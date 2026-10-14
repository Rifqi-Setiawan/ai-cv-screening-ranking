"""Pytest configuration and shared test fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set test environment before importing application
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://cv_screening_user:4ql2MmOgXcZ9p9LPeNsP8JkMe7stZFnf6sAbmQxG1_c@127.0.0.1:5432/cv_screening",
)
os.environ.setdefault("JWT_SECRET", "8058e8757806ab6d42d4127510a6d5b5691e11cf01f04e4a4dac2314846b035c")

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio

from src.api.main import app
from src.domain.auth import create_access_token
from src.domain.models import UserRole

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_token() -> str:
    return create_access_token(
        {
            "sub": "adbbfe35-43d1-40ef-a02b-10c975110219",
            "tenant_id": DEMO_TENANT_ID,
            "email": "admin@rifqisetiawan.my.id",
            "role": UserRole.ADMIN.value,
        }
    )


@pytest.fixture
def recruiter_token() -> str:
    return create_access_token(
        {
            "sub": "ce12fcef-601b-4fb8-b8ed-f3eab5e8de6c",
            "tenant_id": DEMO_TENANT_ID,
            "email": "recruiter@rifqisetiawan.my.id",
            "role": UserRole.RECRUITER.value,
        }
    )


@pytest.fixture
def hiring_manager_token() -> str:
    return create_access_token(
        {
            "sub": "fffb4b73-f806-46df-89b4-3318143ece4a",
            "tenant_id": DEMO_TENANT_ID,
            "email": "manager@rifqisetiawan.my.id",
            "role": UserRole.HIRING_MANAGER.value,
        }
    )
