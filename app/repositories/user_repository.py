"""Repository with low-level data access for users."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserDomain, UserEnv


class UserRepository:
    """Encapsulates SQLAlchemy CRUD operations for `User`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_login(self, login: str) -> User | None:
        """Return user by login if present."""
        stmt = select(User).where(User.login == login)
        result = await self.session.scalars(stmt)
        return result.first()

    async def create_user(
        self,
        login: str,
        encrypted_password: str,
        project_id: UUID,
        env: UserEnv,
        domain: UserDomain,
    ) -> User:
        """Create and flush a user record."""
        user = User(
            login=login,
            password=encrypted_password,
            project_id=project_id,
            env=env,
            domain=domain,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def list_users(
        self,
        *,
        project_id: UUID | None,
        env: UserEnv | None,
        domain: UserDomain | None,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        """Return paginated users list and total count."""
        filters: list[Any] = []
        if project_id is not None:
            filters.append(User.project_id == project_id)
        if env is not None:
            filters.append(User.env == env)
        if domain is not None:
            filters.append(User.domain == domain)

        data_stmt = (
            select(User).where(*filters).order_by(User.created_at.asc()).limit(limit).offset(offset)
        )
        count_stmt = select(func.count()).select_from(User).where(*filters)

        data_result = await self.session.scalars(data_stmt)
        count_result = await self.session.execute(count_stmt)
        return list(data_result.all()), int(count_result.scalar_one())

    async def lock_first_available(
        self,
        *,
        now_utc: datetime,
        lock_until: datetime,
        project_id: UUID | None,
        env: UserEnv | None,
        domain: UserDomain | None,
    ) -> User | None:
        """Lock and return first available user with row-level lock."""
        filters: list[Any] = [or_(User.locktime.is_(None), User.locktime <= now_utc)]
        if project_id is not None:
            filters.append(User.project_id == project_id)
        if env is not None:
            filters.append(User.env == env)
        if domain is not None:
            filters.append(User.domain == domain)

        stmt = select(User).where(*filters).order_by(User.created_at.asc()).limit(1)

        bind = self.session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        result = await self.session.scalars(stmt)
        user = result.first()
        if user is None:
            return None

        user.locktime = lock_until
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def free_all_users(self) -> int:
        """Remove lock from all currently locked users and return affected rows."""
        stmt = update(User).where(User.locktime.is_not(None)).values(locktime=None)
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)
