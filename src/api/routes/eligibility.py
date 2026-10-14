"""Administrative Eligibility Gate rules management and approval endpoints (FX-24)."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user, get_job_for_tenant, require_role
from src.domain.models import User, UserRole
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/jobs/{job_id}/eligibility-rules", tags=["Eligibility Rules"])


class EligibilityRuleCreate(BaseModel):
    category: Literal["AGE", "GENDER"]
    rule_type: Literal["MAX_AGE", "MIN_AGE", "AGE_RANGE", "EXACT_GENDER"]
    parameters: dict[str, Any]
    justification: str = Field(..., min_length=30, description="HR legal justification required by SE Menaker")


@router.get("")
async def list_eligibility_rules(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            """
            SELECT id, tenant_id, job_id, category, rule_type, parameters, justification,
                   is_active, approved_by, approved_at, created_by, created_at
            FROM eligibility_rules
            WHERE job_id = %s AND tenant_id = %s
            ORDER BY created_at ASC
            """,
            (job_id, current_user.tenant_id),
        )
        return [dict(r) for r in await cur.fetchall()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_eligibility_rule(
    job_id: uuid.UUID,
    payload: EligibilityRuleCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        rule_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO eligibility_rules (
                id, tenant_id, job_id, category, rule_type, parameters, justification,
                is_active, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, false, %s)
            RETURNING id, category, rule_type, parameters, justification, is_active, created_at
            """,
            (
                rule_id,
                current_user.tenant_id,
                job_id,
                payload.category,
                payload.rule_type,
                json.dumps(payload.parameters),
                payload.justification,
                current_user.id,
            ),
        )
        row = await cur.fetchone()
        await conn.commit()
        return dict(row)


@router.post("/{rule_id}/approve", status_code=status.HTTP_200_OK)
async def approve_eligibility_rule(
    job_id: uuid.UUID,
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        await cur.execute(
            """
            SELECT id, category, rule_type, justification, is_active
            FROM eligibility_rules
            WHERE id = %s AND job_id = %s AND tenant_id = %s
            """,
            (rule_id, job_id, current_user.tenant_id),
        )
        rule = await cur.fetchone()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aturan eligibility tidak ditemukan")

        await cur.execute(
            """
            UPDATE eligibility_rules
            SET is_active = true, approved_by = %s, approved_at = now()
            WHERE id = %s AND tenant_id = %s
            RETURNING id, category, rule_type, is_active, approved_at
            """,
            (current_user.id, rule_id, current_user.tenant_id),
        )
        updated = await cur.fetchone()

        # Audit trail (immutable compliance log)
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'APPROVE_ELIGIBILITY_RULE', 'eligibility_rule', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                str(rule_id),
                json.dumps(
                    {
                        "job_id": str(job_id),
                        "category": rule["category"],
                        "justification": rule["justification"],
                    }
                ),
            ),
        )
        await conn.commit()
        return dict(updated)


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_eligibility_rule(
    job_id: uuid.UUID,
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            "DELETE FROM eligibility_rules WHERE id = %s AND job_id = %s AND tenant_id = %s RETURNING id",
            (rule_id, job_id, current_user.tenant_id),
        )
        deleted = await cur.fetchone()
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aturan eligibility tidak ditemukan")
        await conn.commit()
        return {"status": "DELETED", "id": str(rule_id)}
