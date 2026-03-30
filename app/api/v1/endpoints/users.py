"""Endpoints implementing botfarm core user flows."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_user_service, require_read_scope, require_write_scope
from app.models.user import User, UserDomain, UserEnv
from app.schemas.user import (
    FreeUsersResponse,
    LockedUserResponse,
    LockUserRequest,
    UserCreateRequest,
    UserListResponse,
    UserPublic,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _to_user_public(user: User) -> UserPublic:
    return UserPublic.model_validate(user)


def _to_locked_user_response(user: User, decrypted_password: str) -> LockedUserResponse:
    if user.locktime is None:
        raise ValueError("Expected non-null locktime for locked user.")
    return LockedUserResponse(
        id=user.id,
        created_at=user.created_at,
        login=user.login,
        password=decrypted_password,
        project_id=user.project_id,
        env=user.env,
        domain=user.domain,
        locktime=user.locktime,
    )


@router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create botfarm user",
)
async def create_user(
    payload: UserCreateRequest,
    service: Annotated[UserService, Depends(get_user_service)],
    _: Annotated[object, Depends(require_write_scope)],
) -> UserPublic:
    """Create a user record and store encrypted credentials."""
    created_user = await service.create_user(payload)
    return _to_user_public(created_user)


@router.get("", response_model=UserListResponse, summary="List users")
async def get_users(
    service: Annotated[UserService, Depends(get_user_service)],
    _: Annotated[object, Depends(require_read_scope)],
    project_id: Annotated[UUID | None, Query()] = None,
    env: Annotated[UserEnv | None, Query()] = None,
    domain: Annotated[UserDomain | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserListResponse:
    """Return all users with optional filtering and pagination."""
    users, total = await service.get_users(
        project_id=project_id,
        env=env,
        domain=domain,
        limit=limit,
        offset=offset,
    )
    return UserListResponse(
        items=[_to_user_public(item) for item in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/lock", response_model=LockedUserResponse, summary="Lock first available user")
async def lock_user(
    payload: LockUserRequest,
    service: Annotated[UserService, Depends(get_user_service)],
    _: Annotated[object, Depends(require_write_scope)],
) -> LockedUserResponse:
    """Lock first available user and return plaintext credentials for E2E."""
    user, plaintext_password = await service.lock_user(payload)
    return _to_locked_user_response(user, plaintext_password)


@router.post("/free", response_model=FreeUsersResponse, summary="Release all locks")
async def free_users(
    service: Annotated[UserService, Depends(get_user_service)],
    _: Annotated[object, Depends(require_write_scope)],
) -> FreeUsersResponse:
    """Clear locktime for every locked user in the system."""
    freed_count = await service.free_users()
    return FreeUsersResponse(freed_count=freed_count)
