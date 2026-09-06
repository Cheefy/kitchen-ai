"""Add user_profile and activity_log.timestamp

Two gaps found while building the BMR/TDEE-based daily deficit view:
there was no user_profile table anywhere despite §2's TDEE calibration
loop assuming a BMR input exists, and activity_log only stored a date
even though Garmin's raw data includes a real start time that
normalize_activity() was silently discarding.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("activity_log", sa.Column("timestamp", sa.DateTime(timezone=False)))

    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("age", sa.Integer, nullable=False),
        sa.Column("biological_sex", sa.String, nullable=False),
        sa.Column("height_cm", sa.Numeric, nullable=False),
        sa.Column("activity_level_override", sa.String),
    )


def downgrade() -> None:
    op.drop_table("user_profile")
    op.drop_column("activity_log", "timestamp")
