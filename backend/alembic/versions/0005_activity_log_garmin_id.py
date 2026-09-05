"""Add activity_log.garmin_activity_id

Gap found while building the Garmin sync (spec §9): re-syncing an
overlapping date range would create duplicate rows with no external ID to
dedupe against.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("activity_log", sa.Column("garmin_activity_id", sa.String, unique=True))


def downgrade() -> None:
    op.drop_column("activity_log", "garmin_activity_id")
