"""Add recommendation_settings fields and user_allergen_restrictions

Two gaps found while building the recommendation engine (spec §8):
enabled_meal_slots / typical_delivery_lead_hours / ingredient_coverage_
threshold are named as settings but were never given columns, and the
"permanent default" allergen restriction the spec assumes has no table
at all in §3.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendation_settings",
        sa.Column(
            "enabled_meal_slots",
            postgresql.JSONB,
            nullable=False,
            server_default='["lunch", "dinner", "treat"]',
        ),
    )
    op.add_column(
        "recommendation_settings",
        sa.Column(
            "typical_delivery_lead_hours", sa.Integer, nullable=False, server_default="5"
        ),
    )
    op.add_column(
        "recommendation_settings",
        sa.Column(
            "ingredient_coverage_threshold", sa.Numeric, nullable=False, server_default="50"
        ),
    )

    op.create_table(
        "user_allergen_restrictions",
        sa.Column("allergen_id", sa.Integer, sa.ForeignKey("allergens.id"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("user_allergen_restrictions")
    op.drop_column("recommendation_settings", "ingredient_coverage_threshold")
    op.drop_column("recommendation_settings", "typical_delivery_lead_hours")
    op.drop_column("recommendation_settings", "enabled_meal_slots")
