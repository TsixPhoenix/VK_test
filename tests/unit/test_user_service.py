"""Unit-style tests for UserService business logic."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.config import Settings
from app.core.exceptions import ConflictError, InternalServiceError, ServiceError
from app.schemas.user import LockUserRequest, UserCreateRequest
from app.services.user_service import UserService
from cryptography.fernet import Fernet
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

    freed_count = await service.free_users_by_scope(
        project_id=None,
        env=None,
        domain=None,
        release_all=True,
    )
    assert freed_count == 1

    relocked_user, relocked_password = await service.lock_user(LockUserRequest())
    assert relocked_user.id == locked_user.id
    assert relocked_password == "VeryStrong1!"


@pytest.mark.asyncio
async def test_free_users_requires_scope_or_explicit_override(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    """Service should reject unscoped unlock requests by default."""
    service = UserService(session=db_session, settings=test_settings)

    with pytest.raises(ServiceError):
        await service.free_users_by_scope(
            project_id=None,
            env=None,
            domain=None,
            release_all=False,
        )


@pytest.mark.asyncio
async def test_lock_user_rolls_back_if_decrypt_fails(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    """Lock must roll back if credential decryption fails after selecting a user."""
    service = UserService(session=db_session, settings=test_settings)
    payload = UserCreateRequest(
        login="rollback@example.com",
        password="VeryStrong1!",
        project_id=uuid4(),
        env="stage",
        domain="regular",
    )
    created = await service.create_user(payload)
    project_id = created.project_id

    wrong_key_settings = test_settings.model_copy(
        update={"botfarm_encryption_key": Fernet.generate_key().decode("utf-8")}
    )
    lock_service = UserService(session=db_session, settings=wrong_key_settings)
    with pytest.raises(InternalServiceError):
        await lock_service.lock_user(LockUserRequest(project_id=project_id))

    users, _ = await service.get_users(
        project_id=project_id,
        env="stage",
        domain="regular",
        limit=10,
        offset=0,
    )
    assert len(users) == 1
    assert users[0].locktime is None
