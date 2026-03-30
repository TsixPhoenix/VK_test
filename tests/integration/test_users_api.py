"""Integration tests for users endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_flow_create_list_lock_free(
    api_client: AsyncClient,
    write_token: str,
    auth_header,
) -> None:
    """Create users, lock them, then release locks."""
    headers = auth_header(write_token)
    project_id = str(uuid4())

    create_first = await api_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "login": "hamster1@example.com",
            "password": "VeryStrong1!",
            "project_id": project_id,
            "env": "stage",
            "domain": "regular",
        },
    )
    assert create_first.status_code == 201

    create_second = await api_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "login": "hamster2@example.com",
            "password": "VeryStrong2!",
            "project_id": project_id,
            "env": "stage",
            "domain": "regular",
        },
    )
    assert create_second.status_code == 201

    list_response = await api_client.get(
        "/api/v1/users",
        headers=headers,
        params={"project_id": project_id, "env": "stage", "domain": "regular"},
    )
    assert list_response.status_code == 200
    listed_payload = list_response.json()
    assert listed_payload["total"] == 2
    assert len(listed_payload["items"]) == 2

    lock_first = await api_client.post(
        "/api/v1/users/locks",
        headers=headers,
        json={"project_id": project_id, "env": "stage", "domain": "regular"},
    )
    assert lock_first.status_code == 201
    first_locked = lock_first.json()
    assert first_locked["password"] == "VeryStrong1!"

    lock_second = await api_client.post(
        "/api/v1/users/locks",
        headers=headers,
        json={"project_id": project_id, "env": "stage", "domain": "regular"},
    )
    assert lock_second.status_code == 201
    second_locked = lock_second.json()
    assert second_locked["password"] == "VeryStrong2!"

    lock_third = await api_client.post(
        "/api/v1/users/locks",
        headers=headers,
        json={"project_id": project_id, "env": "stage", "domain": "regular"},
    )
    assert lock_third.status_code == 409

    free_response = await api_client.request(
        "DELETE",
        "/api/v1/users/locks",
        headers=headers,
        params={"project_id": project_id, "env": "stage", "domain": "regular"},
    )
    assert free_response.status_code == 200
    assert free_response.json()["freed_count"] == 2


@pytest.mark.asyncio
async def test_release_locks_requires_scope_or_explicit_override(
    api_client: AsyncClient,
    write_token: str,
    auth_header,
) -> None:
    """Delete locks endpoint must be scoped or explicitly global."""
    headers = auth_header(write_token)
    response = await api_client.request("DELETE", "/api/v1/users/locks", headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_user_duplicate_login_conflict(
    api_client: AsyncClient,
    write_token: str,
    auth_header,
) -> None:
    """Duplicate login should produce conflict status code."""
    headers = auth_header(write_token)
    payload = {
        "login": "same@example.com",
        "password": "VeryStrong1!",
        "project_id": str(uuid4()),
        "env": "prod",
        "domain": "canary",
    }

    first_response = await api_client.post("/api/v1/users", headers=headers, json=payload)
    second_response = await api_client.post("/api/v1/users", headers=headers, json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_scopes_enforced(
    api_client: AsyncClient,
    read_token: str,
    auth_header,
) -> None:
    """Read-only token should not perform write operations."""
    headers = auth_header(read_token)

    create_response = await api_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "login": "readonly@example.com",
            "password": "VeryStrong1!",
            "project_id": str(uuid4()),
            "env": "stage",
            "domain": "regular",
        },
    )
    assert create_response.status_code == 403

    list_response = await api_client.get("/api/v1/users", headers=headers)
    assert list_response.status_code == 200
