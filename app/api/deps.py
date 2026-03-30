"""FastAPI dependencies used by routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import AUTH_SCOPES, decode_access_token
from app.db.session import get_db_session
from app.schemas.auth import TokenPayload
from app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", scopes=AUTH_SCOPES)


def _build_authenticate_header(security_scopes: SecurityScopes) -> str:
    if not security_scopes.scopes:
        return "Bearer"
    scope_str = " ".join(security_scopes.scopes)
    return f'Bearer scope="{scope_str}"'


async def get_current_token_payload(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPayload:
    """Validate bearer token and enforce required OAuth2 scopes."""
    authenticate_value = _build_authenticate_header(security_scopes)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        payload = decode_access_token(token, settings=settings)
        token_payload = TokenPayload(**payload)
    except (UnauthorizedError, ValidationError) as exc:
        raise credentials_exception from exc

    for required_scope in security_scopes.scopes:
        if required_scope not in token_payload.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions for this operation.",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return token_payload


async def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserService:
    """Build service object with session and settings dependencies."""
    return UserService(session=session, settings=settings)


async def require_read_scope(
    token_payload: Annotated[
        TokenPayload, Security(get_current_token_payload, scopes=["botfarm:read"])
    ],
) -> TokenPayload:
    """Dependency ensuring caller has read scope."""
    return token_payload


async def require_write_scope(
    token_payload: Annotated[
        TokenPayload, Security(get_current_token_payload, scopes=["botfarm:write"])
    ],
) -> TokenPayload:
    """Dependency ensuring caller has write scope."""
    return token_payload
