"""Shared pytest fixtures for botfarm tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

os.environ.setdefault("BOTFARM_ENCRYPTION_KEY", "S19DbgZpUWOxRjlW-z9QbtdomIfRqJfu_m5M6mqwtvI=")
os.environ.setdefault("JWT_SECRET_KEY", "test-super-secret-key")
os.environ.setdefault("AUTH_PASSWORD", "test-password")

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db_session, get_engine, get_session_factory
from app.main import create_app


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Prepare isolated settings for test process."""
    configured_test_db_url = os.getenv("TEST_DATABASE_URL")
    if configured_test_db_url:
        monkeypatch.setenv("DATABASE_URL", configured_test_db_url)
    else:
        db_path = tmp_path / "botfarm_test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("BOTFARM_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-super-secret-key")
    monkeypatch.setenv("AUTH_PASSWORD", "test-password")
    monkeypatch.setenv("LOCK_TTL_SECONDS", "300")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest_asyncio.fixture
async def db_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    """Create isolated database engine and schema for tests."""
    engine = create_async_engine(test_settings.database_url, future=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return async sessionmaker bound to test engine."""
    return async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Provide standalone DB session for service-level tests."""
    async with session_factory() as session:
        yield session


@pytest.fixture
def app(
    test_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
):
    """Create FastAPI app with dependency overrides for tests."""
    application = create_app()

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_get_settings() -> Settings:
        return test_settings

    application.dependency_overrides[get_db_session] = override_get_db_session
    application.dependency_overrides[get_settings] = override_get_settings
    return application


@pytest_asyncio.fixture
async def api_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Provide HTTP client bound directly to ASGI app."""
    transport = ASGITransport(app=app)
    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def write_token(api_client: AsyncClient) -> str:
    """Issue full-access token for test calls."""
    response = await api_client.post(
        "/api/v1/auth/token",
        data={
            "username": "botfarm_admin",
            "password": "test-password",
            "scope": "botfarm:read botfarm:write",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def read_token(api_client: AsyncClient) -> str:
    """Issue read-only token for authorization tests."""
    response = await api_client.post(
        "/api/v1/auth/token",
        data={
            "username": "botfarm_admin",
            "password": "test-password",
            "scope": "botfarm:read",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_header() -> Callable[[str], dict[str, str]]:
    """Return helper creating Authorization header for a token."""

    def _build(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _build
