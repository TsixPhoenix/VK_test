"""OAuth2 authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES, Settings, get_settings
from app.core.security import AUTH_SCOPES, create_access_token, verify_auth_credentials
from app.schemas.auth import TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def issue_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Issue JWT access token for configured service account."""
    is_valid = verify_auth_credentials(
        username=form_data.username,
        password=form_data.password,
        settings=settings,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    requested_scopes = list(dict.fromkeys(form_data.scopes))
    if requested_scopes:
        unknown_scopes = [scope for scope in requested_scopes if scope not in AUTH_SCOPES]
        if unknown_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown scopes requested: {', '.join(unknown_scopes)}",
            )
        granted_scopes = requested_scopes
    else:
        granted_scopes = sorted(AUTH_SCOPES.keys())

    access_token = create_access_token(
        subject=form_data.username,
        scopes=granted_scopes,
        settings=settings,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        scope=" ".join(granted_scopes),
    )
