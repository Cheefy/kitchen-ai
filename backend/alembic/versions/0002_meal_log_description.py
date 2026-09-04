"""Add meal_log.description

An ad-hoc estimate with no recipe/batch/ingredient link had no way to
record what was actually eaten -- gap found while building meal logging,
not in the original spec's field list for this table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("meal_log", sa.Column("description", sa.String))


def downgrade() -> None:
    op.drop_column("meal_log", "description")
