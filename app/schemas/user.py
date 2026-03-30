"""Schemas for user management endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserDomain, UserEnv


class UserCreateRequest(BaseModel):
    """Payload for creating a new botfarm user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "login": "petbuyer@example.com",
                "password": "VeryStrong1!",
                "project_id": "11111111-1111-1111-1111-111111111111",
                "env": "stage",
                "domain": "regular",
            }
        }
    )

    login: EmailStr
    password: str = Field(min_length=8, max_length=128)
    project_id: UUID
    env: UserEnv
    domain: UserDomain


class UserPublic(BaseModel):
    """Public user data that excludes sensitive credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    login: EmailStr
    project_id: UUID
    env: UserEnv
    domain: UserDomain
    locktime: datetime | None


class UserListResponse(BaseModel):
    """Paginated users response."""

    items: list[UserPublic]
    total: int
    limit: int
    offset: int


class LockUserRequest(BaseModel):
    """Optional filters used for selecting locked user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "11111111-1111-1111-1111-111111111111",
                "env": "stage",
                "domain": "regular",
            }
        }
    )

    project_id: UUID | None = None
    env: UserEnv | None = None
    domain: UserDomain | None = None


class LockedUserResponse(BaseModel):
    """Response returned after successful lock operation."""

    id: UUID
    created_at: datetime
    login: EmailStr
    password: str
    project_id: UUID
    env: UserEnv
    domain: UserDomain
    locktime: datetime


class FreeUsersResponse(BaseModel):
    """Response payload for global unlock operation."""

    freed_count: int
