"""Business logic for botfarm users."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LOCK_TTL_SECONDS, Settings
from app.core.exceptions import ConflictError, ServiceError
from app.core.security import decrypt_secret, encrypt_secret
from app.models.user import User, UserDomain, UserEnv
from app.repositories.user_repository import UserRepository
from app.schemas.user import LockUserRequest, UserCreateRequest


class UserService:
    """Coordinates user-related repository operations and business constraints."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = UserRepository(session=session)

    async def create_user(self, payload: UserCreateRequest) -> User:
        """Create a new botfarm user with encrypted password."""
        existing = await self.repository.get_by_login(str(payload.login))
        if existing is not None:
            raise ConflictError(f"User with login `{payload.login}` already exists.")

        encrypted_password = encrypt_secret(payload.password, settings=self.settings)

        try:
            user = await self.repository.create_user(
                login=str(payload.login),
                encrypted_password=encrypted_password,
                project_id=payload.project_id,
                env=payload.env,
                domain=payload.domain,
            )
            await self.session.commit()
            return user
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(f"User with login `{payload.login}` already exists.") from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise ServiceError("Could not create user due to database error.") from exc

    async def get_users(
        self,
        *,
        project_id: UUID | None,
        env: UserEnv | None,
        domain: UserDomain | None,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        """Get users list with optional filters and pagination."""
        try:
            return await self.repository.list_users(
                project_id=project_id,
                env=env,
                domain=domain,
                limit=limit,
                offset=offset,
            )
        except SQLAlchemyError as exc:
            raise ServiceError("Could not fetch users due to database error.") from exc

    async def lock_user(self, payload: LockUserRequest) -> tuple[User, str]:
        """Lock first available user and return it with decrypted password."""
        user: User | None = None
        plaintext_password: str | None = None

        try:
            async with self.session.begin():
                user = await self.repository.lock_first_available(
                    lock_ttl_seconds=LOCK_TTL_SECONDS,
                    project_id=payload.project_id,
                    env=payload.env,
                    domain=payload.domain,
                )
                if user is None:
                    raise ConflictError("No available users to lock for requested filters.")
                plaintext_password = decrypt_secret(user.password, settings=self.settings)
                if user.locktime is None:
                    raise ServiceError("Internal error: locktime was not assigned.")
        except SQLAlchemyError as exc:
            raise ServiceError("Could not lock user due to database error.") from exc

        if user is None or plaintext_password is None:
            raise ServiceError("Internal error: lock transaction returned incomplete data.")
        return user, plaintext_password

    async def free_users_by_scope(
        self,
        *,
        project_id: UUID | None,
        env: UserEnv | None,
        domain: UserDomain | None,
        release_all: bool,
    ) -> int:
        """Remove locktime using explicit scope or an explicit global override."""
        has_filters = any([project_id is not None, env is not None, domain is not None])
        if release_all and has_filters:
            raise ServiceError("`release_all=true` cannot be combined with context filters.")
        if not release_all and not has_filters:
            raise ServiceError(
                "At least one scope filter (`project_id`, `env`, `domain`) is required. "
                "Use `release_all=true` for a global unlock."
            )

        try:
            freed_count = await self.repository.free_users(
                project_id=project_id,
                env=env,
                domain=domain,
                release_all=release_all,
            )
            await self.session.commit()
            return freed_count
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise ServiceError("Could not release users due to database error.") from exc
