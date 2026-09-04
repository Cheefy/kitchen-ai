"""Initial schema (§3 of kitchen_ai_spec.md)

Revision ID: 0001
Revises:
Create Date: 2026-09-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "units",
        sa.Column("code", sa.String, primary_key=True),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("to_canonical_factor", sa.Numeric),
    )

    op.create_table(
        "ingredient_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
    )

    op.create_table(
        "allergens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
    )

    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("upc_barcode", sa.String, unique=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("ingredient_categories.id"), nullable=False),
        sa.Column("calories", sa.Numeric),
        sa.Column("protein_g", sa.Numeric),
        sa.Column("carbs_g", sa.Numeric),
        sa.Column("fat_g", sa.Numeric),
        sa.Column("serving_size", sa.Numeric),
        sa.Column("serving_size_unit", sa.String, nullable=False, server_default="g"),
        sa.Column("saturated_fat_g", sa.Numeric),
        sa.Column("sodium_mg", sa.Numeric),
        sa.Column("fiber_g", sa.Numeric),
        sa.Column("sugars_g", sa.Numeric),
        sa.Column("micronutrients", postgresql.JSONB),
        sa.Column("ingredients_list_raw", sa.Text),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("density_g_per_ml", sa.Numeric),
        sa.Column("unit_weight_g", sa.Numeric),
        sa.Column("unit_label", sa.String),
    )

    op.create_table(
        "ingredient_allergens",
        sa.Column("ingredient_id", sa.Integer, sa.ForeignKey("ingredients.id"), primary_key=True),
        sa.Column("allergen_id", sa.Integer, sa.ForeignKey("allergens.id"), primary_key=True),
    )

    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ingredient_id", sa.Integer, sa.ForeignKey("ingredients.id"), nullable=False),
        sa.Column("quantity", sa.Numeric, nullable=False),
        sa.Column("unit", sa.String, sa.ForeignKey("units.code"), nullable=False),
        sa.Column("expiration_date", sa.Date),
        sa.Column("location", sa.String),
    )

    op.create_table(
        "cookware",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("type", sa.String),
        sa.Column("tare_weight", sa.Numeric),
        sa.Column("label_number", sa.String, unique=True),
    )

    op.create_table(
        "behavior_settings",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("mode", sa.String, nullable=False, server_default="assume_and_announce"),
    )

    op.create_table(
        "system_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("trigger", sa.Text),
        sa.Column("corrected", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("behavior_key", sa.String, sa.ForeignKey("behavior_settings.key")),
        sa.Column("debug_detail", postgresql.JSONB),
    )

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("instructions", sa.Text),
        sa.Column("base_servings", sa.Numeric, nullable=False),
        sa.Column("prep_minutes", sa.Integer),
        sa.Column("active_minutes", sa.Integer),
        sa.Column("passive_minutes", sa.Integer),
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("ingredient_categories.id"), nullable=False),
        sa.Column("quantity", sa.Numeric, nullable=False),
        sa.Column("unit", sa.String, sa.ForeignKey("units.code"), nullable=False),
    )

    op.create_table(
        "recipe_cookware",
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id"), primary_key=True),
        sa.Column("cookware_id", sa.Integer, sa.ForeignKey("cookware.id"), primary_key=True),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "recipe_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("snapshot", postgresql.JSONB, nullable=False),
    )

    op.create_table(
        "shopping_list",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ingredient_id", sa.Integer, sa.ForeignKey("ingredients.id")),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("ingredient_categories.id")),
        sa.Column("quantity_needed", sa.Numeric, nullable=False),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "meal_prep_batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("description", sa.String),
        sa.Column("date_prepared", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("units_total", sa.Numeric, nullable=False),
        sa.Column("units_remaining", sa.Numeric, nullable=False),
        sa.Column("macros_per_unit", postgresql.JSONB, nullable=False),
    )

    op.create_table(
        "meal_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id")),
        sa.Column("meal_prep_batch_id", sa.Integer, sa.ForeignKey("meal_prep_batches.id")),
        sa.Column("ingredient_id", sa.Integer, sa.ForeignKey("ingredients.id")),
        sa.Column("quantity", sa.Numeric),
        sa.Column("macros", postgresql.JSONB, nullable=False),
        sa.Column("is_estimate", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "planned_meals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False, server_default=sa.func.current_date()),
        sa.Column("meal_slot", sa.String, nullable=False),
        sa.Column("description", sa.String),
        sa.Column("estimated_calories", sa.Numeric),
        sa.Column("estimated_protein_g", sa.Numeric),
        sa.Column("estimated_carbs_g", sa.Numeric),
        sa.Column("estimated_fat_g", sa.Numeric),
    )

    op.create_table(
        "weigh_ins",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("weight", sa.Numeric, nullable=False),
    )

    op.create_table(
        "activity_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("activity_type", sa.String),
        sa.Column("duration_minutes", sa.Numeric),
        sa.Column("distance", sa.Numeric),
        sa.Column("calories_burned", sa.Numeric),
    )

    op.create_table(
        "user_goals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("goal_type", sa.String),
        sa.Column("target_deficit_surplus", sa.Numeric),
        sa.Column("protein_g", sa.Numeric),
        sa.Column("fat_g", sa.Numeric),
        sa.Column("carbs_g", sa.Numeric),
        sa.Column("goal_weight", sa.Numeric),
        sa.Column("target_date", sa.Date),
    )

    op.create_table(
        "recommendation_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("calorie_deficit_adherence", sa.Numeric, nullable=False, server_default="80"),
        sa.Column("protein_adherence", sa.Numeric, nullable=False, server_default="80"),
        sa.Column("carb_adherence", sa.Numeric, nullable=False, server_default="20"),
        sa.Column("fat_adherence", sa.Numeric, nullable=False, server_default="20"),
        sa.Column("diversity", sa.Numeric, nullable=False, server_default="50"),
        sa.Column("expiration_urgency", sa.Numeric, nullable=False, server_default="50"),
    )

    # Seed Tier 1 unit conversions (§5) -- fixed physical constants, canonical
    # unit is grams for mass, ml for volume. `count` has no universal factor;
    # it's always resolved per-ingredient via ingredients.unit_weight_g.
    units_table = sa.table(
        "units",
        sa.column("code", sa.String),
        sa.column("type", sa.String),
        sa.column("to_canonical_factor", sa.Numeric),
    )
    op.bulk_insert(
        units_table,
        [
            {"code": "g", "type": "mass", "to_canonical_factor": "1"},
            {"code": "kg", "type": "mass", "to_canonical_factor": "1000"},
            {"code": "oz", "type": "mass", "to_canonical_factor": "28.349523125"},
            {"code": "lb", "type": "mass", "to_canonical_factor": "453.59237"},
            {"code": "ml", "type": "volume", "to_canonical_factor": "1"},
            {"code": "l", "type": "volume", "to_canonical_factor": "1000"},
            {"code": "tsp", "type": "volume", "to_canonical_factor": "4.92892159375"},
            {"code": "tbsp", "type": "volume", "to_canonical_factor": "14.78676478125"},
            {"code": "cup", "type": "volume", "to_canonical_factor": "236.5882365"},
            {"code": "fl_oz", "type": "volume", "to_canonical_factor": "29.5735295625"},
            {"code": "count", "type": "count", "to_canonical_factor": None},
        ],
    )


def downgrade() -> None:
    op.drop_table("recommendation_settings")
    op.drop_table("user_goals")
    op.drop_table("activity_log")
    op.drop_table("weigh_ins")
    op.drop_table("planned_meals")
    op.drop_table("meal_log")
    op.drop_table("meal_prep_batches")
    op.drop_table("shopping_list")
    op.drop_table("recipe_versions")
    op.drop_table("recipe_cookware")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
    op.drop_table("system_log")
    op.drop_table("behavior_settings")
    op.drop_table("cookware")
    op.drop_table("inventory")
    op.drop_table("ingredient_allergens")
    op.drop_table("ingredients")
    op.drop_table("allergens")
    op.drop_table("ingredient_categories")
    op.drop_table("units")
