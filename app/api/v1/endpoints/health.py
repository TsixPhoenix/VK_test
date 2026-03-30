"""Health and probe endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import READINESS_DB_TIMEOUT_SECONDS
from app.db.session import check_database_connection, get_db_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness probe")
async def liveness_probe() -> dict[str, str]:
    """Return app process liveness without external checks."""
    return {"status": "alive"}


@router.get("/ready", summary="Readiness probe")
async def readiness_probe(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Return readiness based on DB connectivity."""
    try:
        await asyncio.wait_for(
            check_database_connection(session),
            timeout=READINESS_DB_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database readiness check timed out.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready.",
        ) from exc

    return {"status": "ready"}


@router.get("/startup", summary="Startup probe")
async def startup_probe(request: Request) -> dict[str, str]:
    """Return startup status once app initialization is complete."""
    startup_complete = bool(getattr(request.app.state, "startup_complete", False))
    if not startup_complete:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application startup is still in progress.",
        )
    return {"status": "started"}
