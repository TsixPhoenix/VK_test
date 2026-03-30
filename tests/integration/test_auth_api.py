"""Integration tests for authentication endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_issue_token_success(api_client: AsyncClient) -> None:
    """Auth endpoint should issue bearer token for valid credentials."""
    response = await api_client.post(
        "/api/v1/auth/token",
        data={"username": "botfarm_admin", "password": "test-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert "botfarm:read" in payload["scope"]
    assert "botfarm:write" in payload["scope"]


@pytest.mark.asyncio
async def test_issue_token_invalid_credentials(api_client: AsyncClient) -> None:
    """Invalid credentials should return 401."""
    response = await api_client.post(
        "/api/v1/auth/token",
        data={"username": "botfarm_admin", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_issue_token_unknown_scope(api_client: AsyncClient) -> None:
    """Unknown OAuth scope should fail request."""
    response = await api_client.post(
        "/api/v1/auth/token",
        data={
            "username": "botfarm_admin",
            "password": "test-password",
            "scope": "botfarm:admin",
        },
    )
    assert response.status_code == 400
