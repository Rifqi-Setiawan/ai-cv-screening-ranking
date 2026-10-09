"""Job openings management routes with role-based access control."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_current_user, require_role
from src.domain.models import JobCreate, JobResponse, User, UserRole
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(current_user: User = Depends(get_current_user)) -> list[JobResponse]:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT id, tenant_id, title, status, location, employment_type, external_ref, created_at
                FROM jobs
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                """,
            (current_user.tenant_id,),
        )
        rows = await cur.fetchall()
        return [
            JobResponse(
                id=r["id"],
                tenant_id=r["tenant_id"],
                title=r["title"],
                status=r["status"],
                location=r["location"],
                employment_type=r["employment_type"],
                external_ref=r["external_ref"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    req: JobCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> JobResponse:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                INSERT INTO jobs (tenant_id, title, jd_text, location, employment_type, external_ref, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, tenant_id, title, status, location, employment_type, external_ref, created_at
                """,
            (
                current_user.tenant_id,
                req.title,
                req.jd_text,
                req.location,
                req.employment_type,
                req.external_ref,
                current_user.id,
            ),
        )
        row = await cur.fetchone()

        # Record audit log
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'JOB_CREATE', 'job', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                str(row["id"]),
                f'{{"title": "{req.title}", "external_ref": "{req.external_ref}"}}',
            ),
        )

        await conn.commit()
        return JobResponse(
            id=row["id"],
            tenant_id=row["tenant_id"],
            title=row["title"],
            status=row["status"],
            location=row["location"],
            employment_type=row["employment_type"],
            external_ref=row["external_ref"],
            created_at=row["created_at"],
        )
