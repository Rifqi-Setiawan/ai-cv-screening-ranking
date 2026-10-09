"""Pytest configuration and shared test fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest_asyncio

from src.api.main import app
from src.domain.auth import create_access_token
from src.infrastructure.database import get_connection, get_db_pool


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    await get_db_pool()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _get_user_token(email: str) -> str:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id, tenant_id, email, role FROM users WHERE email = %s", (email,))
        row = await cur.fetchone()
        assert row is not None, f"Seeded user {email} not found in database"
        return create_access_token(
            {
                "sub": str(row["id"]),
                "tenant_id": str(row["tenant_id"]),
                "email": row["email"],
                "role": row["role"],
            }
        )


@pytest_asyncio.fixture
async def admin_token() -> str:
    return await _get_user_token("admin@rifqisetiawan.my.id")


@pytest_asyncio.fixture
async def recruiter_token() -> str:
    return await _get_user_token("recruiter@rifqisetiawan.my.id")


@pytest_asyncio.fixture
async def hiring_manager_token() -> str:
    return await _get_user_token("manager@rifqisetiawan.my.id")
