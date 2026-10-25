"""timezone-aware timestamps, users.password not null

Revision ID: c92c77fd72d9
Revises: d08e923698cc
Create Date: 2026-10-25 19:29:26.671508

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c92c77fd72d9"
down_revision: str | Sequence[str] | None = "d08e923698cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_COLUMNS = [
    ("users", "created_at"),
    ("users", "updated_at"),
    ("monitors", "created_at"),
    ("monitors", "updated_at"),
]


def upgrade() -> None:
    """Upgrade schema."""
    # Existing values were written in UTC: say so explicitly instead of
    # relying on the server's TimeZone setting.
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=postgresql.TIMESTAMP(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )

    op.alter_column(
        "users",
        "password",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "users",
        "password",
        existing_type=sa.VARCHAR(length=255),
        nullable=True,
    )

    # timestamptz -> timestamp: keep the wall-clock time in UTC
    for table, column in reversed(TIMESTAMP_COLUMNS):
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            type_=postgresql.TIMESTAMP(),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )