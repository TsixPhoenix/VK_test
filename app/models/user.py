"""User entity used by botfarm flows."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class UserEnv(StrEnum):
    """Supported runtime environments for user credentials."""

    prod = "prod"
    preprod = "preprod"
    stage = "stage"


class UserDomain(StrEnum):
    """Supported user domains for usage segregation."""

    canary = "canary"
    regular = "regular"


class User(Base):
    """Botfarm user credentials tied to project and environment."""

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_project_env_domain_created_at",
            "project_id",
            "env",
            "domain",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    login: Mapped[str] = mapped_column(String(length=320), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(length=1024), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    env: Mapped[UserEnv] = mapped_column(
        SAEnum(UserEnv, name="user_env", native_enum=False, create_constraint=True),
        nullable=False,
    )
    domain: Mapped[UserDomain] = mapped_column(
        SAEnum(UserDomain, name="user_domain", native_enum=False, create_constraint=True),
        nullable=False,
    )
    locktime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
