"""Async SQLAlchemy engine and session factory helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create and cache async database engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create and cache async session factory."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a scoped async DB session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def check_database_connection(session: AsyncSession) -> None:
    """Validate DB connectivity with a lightweight query."""
    await session.execute(text("SELECT 1"))


async def dispose_engine() -> None:
    """Dispose cached DB engine."""
    await get_engine().dispose()
