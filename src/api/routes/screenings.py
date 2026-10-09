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
        await cur.execute(
            """
            INSERT INTO screening_runs (
                id, tenant_id, job_id, requirement_set_id, status, as_of, config
            )
            VALUES (%s, %s, %s, %s, 'RUNNING', %s, %s)
            """,
            (
                run_id,
                current_user.tenant_id,
                job_id,
                req_set["id"],
                payload.as_of,
                json.dumps({"use_verifier": payload.use_verifier, "as_of": payload.as_of}),
            ),
        )

        # 4. Fetch all CVs for this job
        await cur.execute(
            """
            SELECT id, file_name, file_hash, matching_profile, full_text_redacted, quality_status, flags, reasons
            FROM cvs
            WHERE job_id = %s
            """,
            (job_id,),
        )
        cv_rows = await cur.fetchall()

        scoring_items: list[dict[str, Any]] = []
        eval_cache: dict[str, dict[str, Any]] = {}

        for cv in cv_rows:
            cv_id = cv["id"]
            file_name = cv["file_name"]
            matching_prof = cv["matching_profile"] or {}
            full_text = cv["full_text_redacted"] or ""
            flags = list(cv["flags"] or [])
            reasons = list(cv["reasons"] or [])

            # Check for edge case quality statuses
            if cv["quality_status"] in ("REJECTED", "NEEDS_REVIEW", "DUPLICATE"):
                eval_cache[str(cv_id)] = {
                    "cv_id": cv_id,
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

            scoring_items.append(
                {
                    "cv_id": cv_id,
                    "file_name": file_name,
                    "result": score_res,
                    "strong_count": strong_count,
                }
            )
            eval_cache[str(cv_id)] = {
                "cv_id": cv_id,
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
            cand_rank = rank_lookup.get(str_cid)
            s_res = c_data["score_res"]

            raw_sc = s_res.raw_score if s_res else 0.0
            fin_sc = s_res.final_score if s_res else 0.0
            bnd = s_res.band if s_res else "R"
            rec = s_res.recommendation if s_res else "MANUAL_CHECK"
            cat_b = s_res.category_breakdown if s_res else {}

            score_id = uuid.uuid4()
            await cur.execute(
                """
                INSERT INTO candidate_scores (
                    id, tenant_id, screening_run_id, cv_id, rank, raw_score, final_score,
                    band, recommendation, category_breakdown, metrics, flags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    score_id,
                    current_user.tenant_id,
                    run_id,
                    cv_id_val,
                    cand_rank,
                    raw_sc,
                    fin_sc,
                    bnd,
                    rec,
                    json.dumps(cat_b),
                    json.dumps(c_data["metrics"]),
                    c_data["flags"],
                ),
            )

            # Insert requirement scores & evidence
            for req_obj in req_set_dict["requirements"]:
                req_id_str = req_obj["requirement_id"]
                st_val = c_data["states"].get(req_id_str, "NOT_DEMONSTRATED")
                ev_list = c_data["evidence"].get(req_id_str, [])

                # Map requirement string ID to DB UUID if available
                req_score_id = uuid.uuid4()
                # Find requirement record uuid
                await cur.execute(
                    """
                    SELECT id FROM requirements
                    WHERE requirement_set_id = %s AND requirement_id = %s
                    LIMIT 1
                    """,
                    (req_set["id"], req_id_str),
                )
                req_row = await cur.fetchone()
                req_db_id = req_row["id"] if req_row else None

                if req_db_id:
                    await cur.execute(
                        """
                        INSERT INTO requirement_scores (
                            id, tenant_id, candidate_score_id, requirement_id, state, confidence
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (req_score_id, current_user.tenant_id, score_id, req_db_id, st_val, 0.95),
                    )

                    for ev_item in ev_list:
                        await cur.execute(
                            """
                            INSERT INTO evidence (
                                id, tenant_id, requirement_score_id, quote, context, verified
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                uuid.uuid4(),
                                current_user.tenant_id,
                                req_score_id,
                                ev_item.get("quote", ""),
                                ev_item.get("context", "experience"),
                                ev_item.get("verified", True),
                            ),
                        )

        # Mark screening run COMPLETED
        await cur.execute(
            "UPDATE screening_runs SET status = 'COMPLETED', completed_at = now() WHERE id = %s",
            (run_id,),
        )
        await conn.commit()

        return {
            "screening_run_id": str(run_id),
            "status": "COMPLETED",
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
            SELECT cs.rank, cs.cv_id, c.file_name, cs.final_score, cs.raw_score,
                   cs.band, cs.recommendation, cs.category_breakdown, cs.flags, c.quality_status
            FROM candidate_scores cs
            JOIN cvs c ON cs.cv_id = c.id
            WHERE cs.screening_run_id = %s
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
            SELECT cs.id, cs.rank, cs.final_score, cs.raw_score, cs.band, cs.recommendation,
                   cs.category_breakdown, cs.metrics, cs.flags, c.file_name
            FROM candidate_scores cs
            JOIN cvs c ON cs.cv_id = c.id
            WHERE cs.screening_run_id = %s AND cs.cv_id = %s
            """,
            (run_id, cv_id),
        )
        cand_score = await cur.fetchone()
        if not cand_score:
            raise HTTPException(status_code=404, detail="Candidate score not found")

        # Fetch requirements and evidence
        await cur.execute(
            """
            SELECT r.requirement_id, r.description, r.category, r.kind, r.importance, r.weight,
                   rs.state, rs.confidence
            FROM requirement_scores rs
            JOIN requirements r ON rs.requirement_id = r.id
            WHERE rs.candidate_score_id = %s
            ORDER BY r.requirement_id
            """,
            (cand_score["id"],),
        )
        req_rows = await cur.fetchall()

        # Build explanation
        req_states = {r["requirement_id"]: r["state"] for r in req_rows}
        ev_map: dict[str, list[dict[str, Any]]] = {}
        for r in req_rows:
            await cur.execute(
                """
                SELECT quote, context, verified
                FROM evidence e
                JOIN requirement_scores rs ON e.requirement_score_id = rs.id
                JOIN requirements req ON rs.requirement_id = req.id
                WHERE rs.candidate_score_id = %s AND req.requirement_id = %s
                """,
                (cand_score["id"], r["requirement_id"]),
            )
            evs = await cur.fetchall()
            ev_map[r["requirement_id"]] = [dict(e) for e in evs]

        # Dummy ScoreResult for explainer
        score_obj = score(
            req_states,
            {
                "category_weights": cand_score["category_breakdown"],
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
            "metrics": cand_score["metrics"],
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

        await cur.execute("SELECT code FROM jobs WHERE id = %s", (job_id,))
        job_row = await cur.fetchone()
        job_code = job_row["code"] if job_row and job_row["code"] else "JD-01"

        await cur.execute("SELECT as_of FROM screening_runs WHERE id = %s", (run_id,))
        run_row = await cur.fetchone()
        as_of = str(run_row["as_of"]) if run_row else "2026-10-01"

        await cur.execute(
            """
            SELECT cs.id as score_id, cs.rank, cs.final_score, cs.raw_score, cs.band,
                   cs.recommendation, cs.category_breakdown, cs.metrics, cs.flags,
                   c.file_name, c.quality_status, c.reasons
            FROM candidate_scores cs
            JOIN cvs c ON cs.cv_id = c.id
            WHERE cs.screening_run_id = %s
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
                SELECT req.requirement_id, rs.state
                FROM requirement_scores rs
                JOIN requirements req ON rs.requirement_id = req.id
                WHERE rs.candidate_score_id = %s
                """,
                (r["score_id"],),
            )
            req_states = {row["requirement_id"]: row["state"] for row in await cur.fetchall()}

            status_val = r["quality_status"] if r["quality_status"] != "READY" else "SCORED"
            export_results.append(
                {
                    "file": r["file_name"],
                    "status": status_val,
                    "rank": r["rank"],
                    "band": r["band"],
                    "score": r["final_score"],
                    "raw_score": r["raw_score"],
                    "recommendation": r["recommendation"],
                    "requirement_states": req_states,
                    "metrics": r["metrics"] or {},
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
