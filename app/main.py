"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import APP_NAME, APP_VERSION, RUN_MIGRATIONS_ON_STARTUP
from app.core.exceptions import ServiceError
from app.db.session import dispose_engine


async def _run_migrations() -> None:
    """Run Alembic migrations in a worker thread."""
    config = Config("alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize app-level state and release resources on shutdown."""
    app.state.startup_complete = False

    if RUN_MIGRATIONS_ON_STARTUP:
        await _run_migrations()

    app.state.startup_complete = True
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Construct and configure FastAPI app."""
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        lifespan=lifespan,
    )
    app.include_router(api_router)

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {"service": APP_NAME, "status": "ok"}

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return app


app = create_app()
