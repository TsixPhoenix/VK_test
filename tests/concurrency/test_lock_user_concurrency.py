"""Concurrency tests for user locking semantics."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.schemas.user import LockUserRequest, UserCreateRequest
from app.services.user_service import UserService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.mark.asyncio
async def test_lock_user_concurrent_requests_issue_single_user(
    test_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Concurrent lock operations must not issue same user twice."""
    if not test_settings.database_url.startswith("postgresql"):
        pytest.skip("Concurrency lock test requires PostgreSQL row-level locking.")

    async with session_factory() as seed_session:
        seed_service = UserService(session=seed_session, settings=test_settings)
        await seed_service.create_user(
            UserCreateRequest(
                login="race@example.com",
                password="VeryStrong1!",
                project_id=uuid4(),
                env="stage",
                domain="regular",
            )
        )

    async def _lock_once() -> str:
        async with session_factory() as worker_session:
            service = UserService(session=worker_session, settings=test_settings)
            user, _ = await service.lock_user(LockUserRequest())
            return str(user.id)

    first_result, second_result = await asyncio.gather(
        _lock_once(),
        _lock_once(),
        return_exceptions=True,
    )

    outcomes = [first_result, second_result]
    successful = [item for item in outcomes if isinstance(item, str)]
    failures = [item for item in outcomes if isinstance(item, Exception)]

    assert len(successful) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], ConflictError)
