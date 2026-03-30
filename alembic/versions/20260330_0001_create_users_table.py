"""create users table

Revision ID: 20260330_0001
Revises:
Create Date: 2026-03-30 00:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260330_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply schema changes for initial users table."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("login", sa.String(length=320), nullable=False),
        sa.Column("password", sa.String(length=1024), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "env",
            sa.Enum(
                "prod",
                "preprod",
                "stage",
                name="user_env",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "domain",
            sa.Enum(
                "canary",
                "regular",
                name="user_domain",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("locktime", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("login", name="uq_users_login"),
    )
    op.create_index("ix_users_project_id", "users", ["project_id"], unique=False)
    op.create_index(
        "ix_users_project_env_domain_created_at",
        "users",
        ["project_id", "env", "domain", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Rollback schema changes for initial users table."""
    op.drop_index("ix_users_project_env_domain_created_at", table_name="users")
    op.drop_index("ix_users_project_id", table_name="users")
    op.drop_table("users")
