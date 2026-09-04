"""Add cooking_sessions

The "one canonical current session" described in spec §1 was never given
a concrete table there -- added while building §6/§7's editing and
session-lifecycle behavior, which both assume it exists. A partial unique
index enforces at most one active session at a time, matching the
single-session model §1 describes.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cooking_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("ingredient_overrides", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("servings_override", sa.Numeric),
    )
    op.create_index(
        "ix_cooking_sessions_one_active",
        "cooking_sessions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("ix_cooking_sessions_one_active", table_name="cooking_sessions")
    op.drop_table("cooking_sessions")
