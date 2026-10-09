"""Tests for health check and operational endpoints."""
from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert data["database"] == "HEALTHY"
    assert data["pgvector_version"] is not None
    assert data["pgvector_version"].startswith("0.8")


@pytest.mark.asyncio
async def test_root_endpoint(client: httpx.AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
