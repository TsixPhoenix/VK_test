"""Unit-style tests for UserService business logic."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.schemas.user import LockUserRequest, UserCreateRequest
from app.services.user_service import UserService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_user_and_get_users(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    """Service should persist created user and return it in list."""
    service = UserService(session=db_session, settings=test_settings)
    payload = UserCreateRequest(
        login="cat@example.com",
        password="VeryStrong1!",
        project_id=uuid4(),
        env="stage",
        domain="regular",
    )

    created_user = await service.create_user(payload)
    users, total = await service.get_users(
        project_id=None,
        env=None,
        domain=None,
        limit=100,
        offset=0,
    )

    assert created_user.login == "cat@example.com"
    assert total == 1
    assert len(users) == 1
    assert users[0].login == "cat@example.com"


@pytest.mark.asyncio
async def test_create_user_duplicate_login_raises_conflict(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    """Duplicate login should be rejected with conflict error."""
    service = UserService(session=db_session, settings=test_settings)
    payload = UserCreateRequest(
        login="dog@example.com",
        password="VeryStrong1!",
        project_id=uuid4(),
        env="prod",
        domain="canary",
    )

    await service.create_user(payload)
    with pytest.raises(ConflictError):
        await service.create_user(payload)


@pytest.mark.asyncio
async def test_lock_user_when_empty_raises_conflict(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    """Lock call should fail when there are no available users."""
    service = UserService(session=db_session, settings=test_settings)

    with pytest.raises(ConflictError):
        await service.lock_user(LockUserRequest())


@pytest.mark.asyncio
async def test_lock_and_free_users(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    """Lock must set locktime and free call must clear all locks."""
    service = UserService(session=db_session, settings=test_settings)
    payload = UserCreateRequest(
        login="parrot@example.com",
        password="VeryStrong1!",
        project_id=uuid4(),
        env="preprod",
        domain="regular",
    )
    await service.create_user(payload)

    locked_user, plaintext_password = await service.lock_user(LockUserRequest())
    assert plaintext_password == "VeryStrong1!"
    assert locked_user.locktime is not None

    with pytest.raises(ConflictError):
        await service.lock_user(LockUserRequest())

    freed_count = await service.free_users()
    assert freed_count == 1

    relocked_user, relocked_password = await service.lock_user(LockUserRequest())
    assert relocked_user.id == locked_user.id
    assert relocked_password == "VeryStrong1!"
