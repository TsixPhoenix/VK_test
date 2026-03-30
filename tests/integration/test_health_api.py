"""Integration tests for health probes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_probe(api_client: AsyncClient) -> None:
    """Liveness endpoint should always return alive."""
    response = await api_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_startup_probe(api_client: AsyncClient) -> None:
    """Startup probe should report started after app lifespan startup."""
    response = await api_client.get("/api/v1/health/startup")
    assert response.status_code == 200
    assert response.json() == {"status": "started"}


@pytest.mark.asyncio
async def test_readiness_probe(api_client: AsyncClient) -> None:
    """Readiness probe should return ready while DB is accessible."""
    response = await api_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
