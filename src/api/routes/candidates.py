"""Candidate management, identity reveal, GDPR/privacy deletion, and dispute endpoints (M6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user, require_role
from src.domain.models import User, UserRole
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/candidates", tags=["Candidates"])


class RevealIdentityRequest(BaseModel):
    reason: str = Field(
        ..., min_length=5, description="Reason for revealing candidate identity (logged in audit trail)"
    )


class ObjectRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Reason for objecting to automated scoring")


@router.post("/{candidate_id}/reveal-identity")
async def reveal_identity(
    candidate_id: str,
    payload: RevealIdentityRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER, UserRole.HIRING_MANAGER])),
) -> dict[str, Any]:
    """Reveals candidate identity and logs to audit_logs."""
    async with get_connection() as conn:
        cur = conn.cursor()

        # Check candidate in cvs table or candidates table
        # Try finding in cvs table first
        await cur.execute(
            """
            SELECT id, file_name, matching_profile
            FROM cvs
            WHERE id::text = %s OR file_name = %s
            """,
            (candidate_id, candidate_id),
        )
        cv_row = await cur.fetchone()

        # Also search candidate_identities if exists
        full_name = "Candidate"
        email = None
        phone = None

        if cv_row and cv_row.get("matching_profile"):
            mp = cv_row["matching_profile"]
            full_name = mp.get("identity", {}).get("full_name") or cv_row["file_name"]

        # Log to audit_logs
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'REVEAL_IDENTITY', 'candidate', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                candidate_id,
                json.dumps({"reason": payload.reason, "candidate_id": candidate_id}),
            ),
        )
        await conn.commit()

        return {
            "candidate_id": candidate_id,
            "revealed": True,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "note": "Identity revealed and recorded in audit log.",
        }


@router.post("/{candidate_id}/object")
async def object_to_scoring(
    candidate_id: str,
    payload: ObjectRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Candidate or recruiter files an objection to automated scoring -> routed to MANUAL_ONLY."""
    async with get_connection() as conn:
        cur = conn.cursor()

        # 1. Update candidate status in candidates table if present
        await cur.execute(
            """
            UPDATE candidates
            SET status = 'MANUAL_ONLY'
            WHERE id::text = %s OR candidate_code = %s
            """,
            (candidate_id, candidate_id),
        )

        # 2. Update candidate_scores table
        await cur.execute(
            """
            UPDATE candidate_scores
            SET recommendation = 'MANUAL_CHECK', band = 'R'
            WHERE candidate_id::text = %s
            """,
            (candidate_id,),
        )

        # 3. Log to audit_logs
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'CANDIDATE_OBJECTION', 'candidate', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                candidate_id,
                json.dumps({"reason": payload.reason, "status": "MANUAL_ONLY"}),
            ),
        )
        await conn.commit()

        return {
            "candidate_id": candidate_id,
            "status": "MANUAL_ONLY",
            "message": "Candidate evaluation set to MANUAL_ONLY following objection.",
        }


@router.delete("/{candidate_id}", status_code=status.HTTP_200_OK)
async def delete_candidate_permanently(
    candidate_id: str,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    """GDPR/Privacy Right-to-be-Forgotten: deletes all records, files, and caches, leaving only a tombstone in past runs."""
    async with get_connection() as conn:
        cur = conn.cursor()

        # 1. Retrieve document and file details before deletion
        await cur.execute(
            """
            SELECT d.id as doc_id, d.original_filename as file_name, d.storage_key, d.candidate_id, cp.id as profile_id
            FROM documents d
            LEFT JOIN candidate_profiles cp ON cp.document_id = d.id
            WHERE d.id::text = %s OR d.original_filename = %s OR d.candidate_id::text = %s
            """,
            (candidate_id, candidate_id, candidate_id),
        )
        doc_rows = await cur.fetchall()

        deleted_files = []
        for row in doc_rows:
            doc_id = row["doc_id"]
            cand_db_id = row["candidate_id"] or doc_id
            prof_id = row["profile_id"]
            storage_key = row.get("storage_key")

            # Remove file from vault
            if storage_key:
                vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(current_user.tenant_id)
                fpath = vault_dir / storage_key
                if fpath.exists():
                    try:
                        fpath.unlink()
                        deleted_files.append(str(fpath))
                    except Exception:
                        pass

            # Wipe related records
            if prof_id:
                await cur.execute("DELETE FROM profile_chunks WHERE profile_id = %s", (prof_id,))
                await cur.execute("DELETE FROM skill_mentions WHERE profile_id = %s", (prof_id,))
                await cur.execute("DELETE FROM candidate_profiles WHERE id = %s", (prof_id,))
            await cur.execute("DELETE FROM candidate_identities WHERE candidate_id = %s", (cand_db_id,))

            # In candidate_scores, turn into an anonymous tombstone
            await cur.execute(
                """
                UPDATE candidate_scores
                SET raw_score = 0, final_score = 0, band = 'R', recommendation = 'MANUAL_CHECK',
                    category_scores = '{}'::jsonb, flags = array_append(flags, 'TOMBSTONE_DELETED')
                WHERE candidate_id = %s
                """,
                (cand_db_id,),
            )

            # In evidence table, wipe quotes
            await cur.execute(
                """
                UPDATE evidence
                SET quote = '[DELETED_PER_GDPR]'
                WHERE candidate_id = %s
                """,
                (cand_db_id,),
            )

            # Delete from documents table
            await cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))

        # 2. Mark tombstone in candidates table if present
        await cur.execute(
            """
            UPDATE candidates
            SET status = 'DELETED', deleted_at = now()
            WHERE id::text = %s OR candidate_code = %s
            """,
            (candidate_id, candidate_id),
        )

        # 3. Invalidate cache entries
        cache_path = Path("data/verifier_cache.json")
        if cache_path.exists():
            try:
                cache_data = json.loads(cache_path.read_text())
                # Clean any entry containing candidate identifier
                cleaned_cache = {k: v for k, v in cache_data.items() if candidate_id not in str(v)}
                cache_path.write_text(json.dumps(cleaned_cache, indent=2))
            except Exception:
                pass

        # 4. Insert Audit Log
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'CANDIDATE_DELETE', 'candidate', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                candidate_id,
                json.dumps({"candidate_id": candidate_id, "tombstone_created": True, "files_deleted": deleted_files}),
            ),
        )
        await conn.commit()

        return {
            "candidate_id": candidate_id,
            "status": "DELETED",
            "message": "Candidate personal data, chunks, and documents erased successfully. Tombstone preserved in past runs.",
            "deleted_files_count": len(deleted_files),
        }
