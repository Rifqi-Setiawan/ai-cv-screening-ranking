"""Health and operational readiness check endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from src.domain.models import HealthResponse
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def check_health() -> HealthResponse:
    db_status = "DOWN"
    pgvector_ver = None
    try:
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1")
            await cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            row = await cur.fetchone()
            if row:
                pgvector_ver = row["extversion"]
            db_status = "HEALTHY"
    except Exception as e:
        db_status = f"ERROR: {str(e)}"

    return HealthResponse(
        status="UP" if db_status == "HEALTHY" else "DEGRADED",
        app_env=settings.APP_ENV,
        database=db_status,
        pgvector_version=pgvector_ver,
        active_services=["api", "postgres", "caddy"],
        timestamp=datetime.now(UTC),
    )
