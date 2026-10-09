"""Pytest configuration and shared test fixtures."""
from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio

from src.api.main import app
from src.domain.auth import create_access_token
from src.domain.models import UserRole
from src.infrastructure.database import get_db_pool


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    await get_db_pool()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_token() -> str:
    return create_access_token(
        {
            "sub": "0b2b4670-4171-4da7-b2c0-fe2150c5d533",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "email": "admin@rifqisetiawan.my.id",
            "role": UserRole.ADMIN.value,
        }
    )


@pytest.fixture
def recruiter_token() -> str:
    return create_access_token(
        {
            "sub": "f5191686-b96e-4d7f-9d74-64897c5790ab",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "email": "recruiter@rifqisetiawan.my.id",
            "role": UserRole.RECRUITER.value,
        }
    )


@pytest.fixture
def hiring_manager_token() -> str:
    return create_access_token(
        {
            "sub": "b9d1be98-895a-4110-b86a-84cc0ffff185",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "email": "manager@rifqisetiawan.my.id",
            "role": UserRole.HIRING_MANAGER.value,
        }
    )
