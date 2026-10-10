"""Screening runs, candidate ranking, comparison, and evaluation export endpoints (M4)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user, require_role
from src.domain.explainer import generate_explanation
from src.domain.kind_rules import (
    eval_achievement,
    eval_certification,
    eval_education,
    eval_experience_duration,
    eval_leadership,
    eval_responsibility,
    eval_skill,
)
from src.domain.models import User, UserRole
from src.domain.scorer import rank, score
from src.domain.verifier import verify_requirement_with_llm
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/jobs/{job_id}/screenings", tags=["Screenings"])


class ScreeningRunCreate(BaseModel):
    as_of: str = Field(default="2026-10-01", description="As-of date for evaluation")
    use_verifier: bool = Field(default=False, description="Enable LLM verification for ambiguous criteria")


@router.post("", status_code=status.HTTP_201_CREATED)
async def trigger_screening_run(
    job_id: uuid.UUID,
    payload: ScreeningRunCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER, UserRole.HIRING_MANAGER])),
) -> dict[str, Any]:
    """Triggers an immutable screening run over all ready CVs for the job."""
    async with get_connection() as conn:
        cur = conn.cursor()

        # 1. Fetch latest approved requirement set for the job
        await cur.execute(
            """
            SELECT id, version, category_weights FROM requirement_sets
            WHERE job_id = %s AND status = 'APPROVED'
            ORDER BY version DESC LIMIT 1
            """,
            (job_id,),
        )
        req_set = await cur.fetchone()
        if not req_set:
            # Fallback to latest requirement set regardless of status for testing
            await cur.execute(
                """
                SELECT id, version, category_weights FROM requirement_sets
                WHERE job_id = %s
                ORDER BY version DESC LIMIT 1
                """,
                (job_id,),
            )
            req_set = await cur.fetchone()

        if not req_set:
            raise HTTPException(status_code=404, detail="No requirement set found for job")

        # 2. Fetch requirements in set
        await cur.execute(
            """
            SELECT requirement_id, description, category, kind, importance, weight, concepts, params
            FROM requirements
            WHERE requirement_set_id = %s
            ORDER BY requirement_id
            """,
            (req_set["id"],),
        )
        requirements = await cur.fetchall()
        if not requirements:
            raise HTTPException(status_code=400, detail="Requirement set has no requirements")

        req_set_dict = {
            "category_weights": req_set["category_weights"],
            "requirements": [dict(r) for r in requirements],
        }

        # 3. Create immutable screening run record
        run_id = uuid.uuid4()
        versions_info = {
            "extractor": "cv-extractor 1.0.0",
            "embedding": "microsoft/harrier-oss-v1-270m",
            "scoring": "1.0.0",
        }
        await cur.execute(
            """
            INSERT INTO screening_runs (
                id, tenant_id, job_id, requirement_set_id, status, as_of, versions, params
            )
            VALUES (%s, %s, %s, %s, 'RUNNING', %s, %s, %s)
            """,
            (
                run_id,
                current_user.tenant_id,
                job_id,
                req_set["id"],
                payload.as_of,
                json.dumps(versions_info),
                json.dumps({"use_verifier": payload.use_verifier, "as_of": payload.as_of}),
            ),
        )

        # 4. Fetch all documents and candidate profiles for this job
        await cur.execute(
            """
            SELECT d.id as document_id, d.original_filename as file_name, d.sha256 as file_hash,
                   d.status as quality_status, d.flags, d.reasons, d.candidate_id,
                   cp.matching_profile
            FROM documents d
            LEFT JOIN candidate_profiles cp ON cp.document_id = d.id
            WHERE d.job_id = %s
            """,
            (job_id,),
        )
        cv_rows = await cur.fetchall()

        scoring_items: list[dict[str, Any]] = []
        eval_cache: dict[str, dict[str, Any]] = {}

        for cv in cv_rows:
            doc_id = cv["document_id"]
            cand_id = cv["candidate_id"] or doc_id
            file_name = cv["file_name"]
            matching_prof = cv["matching_profile"] or {}
            full_text = ""
            flags = list(cv["flags"] or [])
            reasons = list(cv["reasons"] or [])

            # Check for edge case quality statuses
            if cv["quality_status"] in ("REJECTED", "NEEDS_REVIEW", "DUPLICATE"):
                eval_cache[str(cand_id)] = {
                    "cv_id": cand_id,
                    "document_id": doc_id,
                    "file_name": file_name,
                    "status": cv["quality_status"],
                    "states": {},
                    "metrics": {},
                    "evidence": {},
                    "flags": flags,
                    "reasons": reasons,
                    "score_res": None,
                }
                continue

            # Evaluate each requirement
            states_map: dict[str, str] = {}
            metrics_map: dict[str, Any] = {}
            ev_map: dict[str, list[dict[str, Any]]] = {}

            for r in req_set_dict["requirements"]:
                rid = r["requirement_id"]
                kind = r["kind"]
                if kind == "EXPERIENCE_DURATION":
                    st, conf, m, evs, flgs = eval_experience_duration(matching_prof, r, as_of=payload.as_of)
                    metrics_map.update(m)
                elif kind == "SKILL":
                    st, conf, m, evs, flgs = eval_skill(matching_prof, r)
                elif kind == "RESPONSIBILITY":
                    st, conf, m, evs, flgs = eval_responsibility(matching_prof, r)
                elif kind == "EDUCATION":
                    st, conf, m, evs, flgs = eval_education(matching_prof, r)
                elif kind == "CERTIFICATION":
                    st, conf, m, evs, flgs = eval_certification(matching_prof, r)
                elif kind == "ACHIEVEMENT":
                    st, conf, m, evs, flgs = eval_achievement(matching_prof, r)
                elif kind == "LEADERSHIP":
                    st, _conf, m, evs, flgs = eval_leadership(matching_prof, r)
                else:
                    st, _conf, m, evs, flgs = "NOT_DEMONSTRATED", 0.9, {}, [], []

                flags.extend(flgs)

                # Optional LLM verifier
                if payload.use_verifier and st in ("PARTIAL", "STRONG") and evs:
                    v_st, v_quote, v_flgs = verify_requirement_with_llm(
                        full_text, r, st, [e.get("quote", "") for e in evs]
                    )
                    st = v_st
                    flags.extend(v_flgs)

                states_map[rid] = st
                ev_map[rid] = evs

            # Calculate deterministic score
            score_res = score(states_map, req_set_dict)
            strong_count = sum(1 for v in states_map.values() if v == "STRONG")

            # Ensure candidate exists in candidates table
            await cur.execute(
                """
                INSERT INTO candidates (id, tenant_id, candidate_code, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                ON CONFLICT (id) DO NOTHING
                """,
                (cand_id, current_user.tenant_id, f"C-{str(cand_id)[:6]}"),
            )

            scoring_items.append(
                {
                    "candidate_id": str(cand_id),
                    "cv_id": cand_id,
                    "document_id": doc_id,
                    "file_name": file_name,
                    "result": score_res,
                    "strong_count": strong_count,
                }
            )
            eval_cache[str(cand_id)] = {
                "cv_id": cand_id,
                "document_id": doc_id,
                "file_name": file_name,
                "status": "SCORED",
                "states": states_map,
                "metrics": metrics_map,
                "evidence": ev_map,
                "flags": flags,
                "reasons": reasons,
                "score_res": score_res,
            }

        # 5. Deterministic tie-broken ranking
        ranked_items = rank(scoring_items, run_id=str(run_id))
        rank_lookup = {str(item["cv_id"]): idx + 1 for idx, item in enumerate(ranked_items)}

        # 6. Save candidate_scores, requirement_scores, and evidence into DB
        for str_cid, c_data in eval_cache.items():
            cv_id_val = c_data["cv_id"]
            doc_id_val = c_data["document_id"]
            cand_rank = rank_lookup.get(str_cid)
            s_res = c_data["score_res"]

            raw_sc = s_res.raw_score if s_res else 0.0
            fin_sc = s_res.final_score if s_res else 0.0
            bnd = s_res.band if s_res else "R"
            rec = s_res.recommendation if s_res else "MANUAL_CHECK"
            cat_b = s_res.category_breakdown if s_res else {}

            await cur.execute(
                """
                INSERT INTO candidate_scores (
                    run_id, candidate_id, tenant_id, document_id, rank, band,
                    raw_score, final_score, capped, recommendation, category_scores, flags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s, %s)
                ON CONFLICT (run_id, candidate_id) DO UPDATE SET
                    rank = EXCLUDED.rank, final_score = EXCLUDED.final_score
                """,
                (
                    run_id,
                    cv_id_val,
                    current_user.tenant_id,
                    doc_id_val,
                    cand_rank,
                    bnd,
                    raw_sc,
                    fin_sc,
                    rec,
                    json.dumps(cat_b),
                    c_data["flags"],
                ),
            )

            # Insert requirement scores & evidence
            for req_obj in req_set_dict["requirements"]:
                req_id_str = req_obj["requirement_id"]
                st_val = c_data["states"].get(req_id_str, "NOT_DEMONSTRATED")
                ev_list = c_data["evidence"].get(req_id_str, [])

                await cur.execute(
                    """
                    INSERT INTO requirement_scores (
                        run_id, candidate_id, requirement_id, tenant_id, state, confidence, method, metrics
                    )
                    VALUES (%s, %s, %s, %s, %s, 0.95, 'rule', '{}'::jsonb)
                    ON CONFLICT (run_id, candidate_id, requirement_id) DO NOTHING
                    """,
                    (run_id, cv_id_val, req_id_str, current_user.tenant_id, st_val),
                )

                for ev_item in ev_list:
                    await cur.execute(
                        """
                        INSERT INTO evidence (
                            id, run_id, candidate_id, requirement_id, tenant_id, quote, context, verified
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            uuid.uuid4(),
                            run_id,
                            cv_id_val,
                            req_id_str,
                            current_user.tenant_id,
                            ev_item.get("quote", ""),
                            ev_item.get("context", "experience"),
                            ev_item.get("verified", True),
                        ),
                    )

        # Mark screening run DONE
        await cur.execute(
            "UPDATE screening_runs SET status = 'DONE', finished_at = now() WHERE id = %s",
            (run_id,),
        )
        await conn.commit()

        return {
            "screening_run_id": str(run_id),
            "status": "DONE",
            "as_of": payload.as_of,
            "total_candidates": len(cv_rows),
            "scored_candidates": len(scoring_items),
        }


@router.get("/{run_id}/rankings")
async def get_rankings(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns candidate rankings for a completed screening run."""
    async with get_connection() as conn:
        cur = conn.cursor()
        await cur.execute(
            """
            SELECT cs.rank, cs.candidate_id as cv_id, cs.candidate_id, d.original_filename as file_name, cs.final_score, cs.raw_score,
                   cs.band, cs.recommendation, cs.category_scores as category_breakdown, cs.flags, d.status as quality_status
            FROM candidate_scores cs
            JOIN documents d ON cs.document_id = d.id
            WHERE cs.run_id = %s
            ORDER BY cs.rank ASC NULLS LAST, cs.final_score DESC
            """,
            (run_id,),
        )
        rows = await cur.fetchall()
        return {
            "job_id": str(job_id),
            "screening_run_id": str(run_id),
            "rankings": [dict(r) for r in rows],
        }


@router.get("/{run_id}/candidates/{cv_id}")
async def get_candidate_detail(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    cv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns detailed evaluation, requirement states, evidence quotes, and template reasoning."""
    async with get_connection() as conn:
        cur = conn.cursor()

        # Fetch candidate score
        await cur.execute(
            """
            SELECT cs.rank, cs.final_score, cs.raw_score, cs.band, cs.recommendation,
                   cs.category_scores as category_breakdown, cs.flags, d.original_filename as file_name
            FROM candidate_scores cs
            JOIN documents d ON cs.document_id = d.id
            WHERE cs.run_id = %s AND cs.candidate_id = %s
            """,
            (run_id, cv_id),
        )
        cand_score = await cur.fetchone()
        if not cand_score:
            raise HTTPException(status_code=404, detail="Candidate score not found")

        # Fetch requirements and states
        await cur.execute(
            """
            SELECT rs.requirement_id, rs.state, rs.confidence,
                   COALESCE(r.description, rs.requirement_id) as description,
                   COALESCE(r.category, 'HARD_SKILLS') as category,
                   COALESCE(r.kind, 'SKILL') as kind,
                   COALESCE(r.importance, 'MUST_HAVE') as importance,
                   COALESCE(r.weight, 10.0) as weight,
                   r.source_text
            FROM requirement_scores rs
            JOIN screening_runs sr ON sr.id = rs.run_id
            LEFT JOIN requirements r ON r.requirement_set_id = sr.requirement_set_id AND r.requirement_id = rs.requirement_id
            WHERE rs.run_id = %s AND rs.candidate_id = %s
            ORDER BY rs.requirement_id
            """,
            (run_id, cv_id),
        )
        req_rows = await cur.fetchall()

        # Build explanation
        req_states = {r["requirement_id"]: r["state"] for r in req_rows}
        ev_map: dict[str, list[dict[str, Any]]] = {}
        for r in req_rows:
            await cur.execute(
                """
                SELECT quote, context, verified
                FROM evidence
                WHERE run_id = %s AND candidate_id = %s AND requirement_id = %s
                """,
                (run_id, cv_id, r["requirement_id"]),
            )
            evs = await cur.fetchall()
            ev_map[r["requirement_id"]] = [dict(e) for e in evs]

        # ScoreResult for explainer
        cat_weights = cand_score["category_breakdown"] or {
            "EXPERIENCE": 40,
            "HARD_SKILLS": 30,
            "EDUCATION_CERT": 15,
            "ACHIEVEMENT": 15,
        }
        score_obj = score(
            req_states,
            {
                "category_weights": cat_weights,
                "requirements": [dict(r) for r in req_rows],
            },
        )
        explanation = generate_explanation(
            {"requirements": [dict(r) for r in req_rows]},
            score_obj,
            req_states,
            ev_map,
        )

        return {
            "cv_id": str(cv_id),
            "file_name": cand_score["file_name"],
            "rank": cand_score["rank"],
            "score": cand_score["final_score"],
            "band": cand_score["band"],
            "recommendation": cand_score["recommendation"],
            "category_breakdown": cand_score["category_breakdown"],
            "metrics": {},
            "flags": cand_score["flags"],
            "requirement_states": req_states,
            "evidence": ev_map,
            "explanation": explanation,
        }


@router.get("/{run_id}/compare")
async def compare_candidates(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    c1: uuid.UUID = Query(..., description="First CV ID"),
    c2: uuid.UUID = Query(..., description="Second CV ID"),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns side-by-side comparison of two candidates."""
    det1 = await get_candidate_detail(job_id, run_id, c1, current_user)
    det2 = await get_candidate_detail(job_id, run_id, c2, current_user)

    all_req_ids = sorted(list(set(det1["requirement_states"].keys()) | set(det2["requirement_states"].keys())))
    req_comparison = []
    for rid in all_req_ids:
        req_comparison.append(
            {
                "requirement_id": rid,
                "candidate_1_state": det1["requirement_states"].get(rid),
                "candidate_2_state": det2["requirement_states"].get(rid),
                "candidate_1_quote": det1["evidence"].get(rid, [{}])[0].get("quote")
                if det1["evidence"].get(rid)
                else "",
                "candidate_2_quote": det2["evidence"].get(rid, [{}])[0].get("quote")
                if det2["evidence"].get(rid)
                else "",
            }
        )

    return {
        "candidate_1": {
            "cv_id": str(c1),
            "file_name": det1["file_name"],
            "rank": det1["rank"],
            "score": det1["score"],
            "band": det1["band"],
            "recommendation": det1["recommendation"],
        },
        "candidate_2": {
            "cv_id": str(c2),
            "file_name": det2["file_name"],
            "rank": det2["rank"],
            "score": det2["score"],
            "band": det2["band"],
            "recommendation": det2["recommendation"],
        },
        "score_delta": round(det1["score"] - det2["score"], 2),
        "requirement_comparison": req_comparison,
    }


@router.get("/{run_id}/eval-export")
async def export_for_evaluator(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Exports run results matching exact eval_export.schema.json format for evaluate.py."""
    async with get_connection() as conn:
        cur = conn.cursor()

        await cur.execute("SELECT external_ref as code FROM jobs WHERE id = %s", (job_id,))
        job_row = await cur.fetchone()
        job_code = job_row["code"] if job_row and job_row["code"] else "JD-01"

        await cur.execute("SELECT as_of FROM screening_runs WHERE id = %s", (run_id,))
        run_row = await cur.fetchone()
        as_of = str(run_row["as_of"]) if run_row else "2026-10-01"

        await cur.execute(
            """
            SELECT cs.candidate_id as cv_id, cs.rank, cs.final_score, cs.raw_score, cs.band,
                   cs.recommendation, cs.category_scores as category_breakdown, cs.flags,
                   d.original_filename as file_name, d.status as quality_status, d.reasons
            FROM candidate_scores cs
            JOIN documents d ON cs.document_id = d.id
            WHERE cs.run_id = %s
            ORDER BY cs.rank ASC NULLS LAST
            """,
            (run_id,),
        )
        score_rows = await cur.fetchall()

        export_results = []
        for r in score_rows:
            # Fetch requirement states
            await cur.execute(
                """
                SELECT requirement_id, state
                FROM requirement_scores
                WHERE run_id = %s AND candidate_id = %s
                """,
                (run_id, r["cv_id"]),
            )
            req_states = {row["requirement_id"]: row["state"] for row in await cur.fetchall()}

            status_val = r["quality_status"] if r["quality_status"] != "READY" else "SCORED"
            export_results.append(
                {
                    "file": r["file_name"],
                    "status": status_val,
                    "rank": r["rank"],
                    "band": r["band"],
                    "score": float(r["final_score"] or 0),
                    "raw_score": float(r["raw_score"] or 0),
                    "recommendation": r["recommendation"],
                    "requirement_states": req_states,
                    "metrics": {},
                    "flags": r["flags"] or [],
                    "reasons": r["reasons"] or [],
                }
            )

        return {
            "job_id": job_code,
            "run_id": str(run_id),
            "as_of": as_of,
            "results": export_results,
        }
