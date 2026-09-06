"""ORM models mirroring §3 of kitchen_ai_spec.md. Keep the two in sync."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# --- Core reference data ---------------------------------------------------


class Unit(Base):
    __tablename__ = "units"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # mass | volume | count
    to_canonical_factor: Mapped[Decimal | None] = mapped_column(Numeric)


class IngredientCategory(Base):
    __tablename__ = "ingredient_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class Allergen(Base):
    __tablename__ = "allergens"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    upc_barcode: Mapped[str | None] = mapped_column(String, unique=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("ingredient_categories.id"), nullable=False)

    calories: Mapped[Decimal | None] = mapped_column(Numeric)
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric)
    carbs_g: Mapped[Decimal | None] = mapped_column(Numeric)
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric)
    serving_size: Mapped[Decimal | None] = mapped_column(Numeric)
    serving_size_unit: Mapped[str] = mapped_column(String, nullable=False, default="g")
    saturated_fat_g: Mapped[Decimal | None] = mapped_column(Numeric)
    sodium_mg: Mapped[Decimal | None] = mapped_column(Numeric)
    fiber_g: Mapped[Decimal | None] = mapped_column(Numeric)
    sugars_g: Mapped[Decimal | None] = mapped_column(Numeric)
    micronutrients: Mapped[dict | None] = mapped_column(JSONB)

    ingredients_list_raw: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, nullable=False)

    # Unit conversion, §5
    density_g_per_ml: Mapped[Decimal | None] = mapped_column(Numeric)
    unit_weight_g: Mapped[Decimal | None] = mapped_column(Numeric)
    unit_label: Mapped[str | None] = mapped_column(String)


class IngredientAllergen(Base):
    __tablename__ = "ingredient_allergens"

    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), primary_key=True)
    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)


class InventoryItem(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(ForeignKey("units.code"), nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String)


class Cookware(Base):
    __tablename__ = "cookware"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str | None] = mapped_column(String)
    tare_weight: Mapped[Decimal | None] = mapped_column(Numeric)
    label_number: Mapped[str | None] = mapped_column(String, unique=True)


# --- Behavior & logging ------------------------------------------------------


class BehaviorSetting(Base):
    __tablename__ = "behavior_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    mode: Mapped[str] = mapped_column(String, nullable=False, default="assume_and_announce")


class SystemLog(Base):
    __tablename__ = "system_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str | None] = mapped_column(Text)
    corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    behavior_key: Mapped[str | None] = mapped_column(ForeignKey("behavior_settings.key"))
    # Populated only when debug mode is on: raw transcript, parsed intent,
    # confidence scores, DB reads/writes, before/after values, session snapshot.
    debug_detail: Mapped[dict | None] = mapped_column(JSONB)


# --- Recipes -----------------------------------------------------------------


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    base_servings: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    prep_minutes: Mapped[int | None] = mapped_column()
    active_minutes: Mapped[int | None] = mapped_column()
    passive_minutes: Mapped[int | None] = mapped_column()
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    cookware_requirements: Mapped[list["RecipeCookware"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("ingredient_categories.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(ForeignKey("units.code"), nullable=False)
    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")


class RecipeCookware(Base):
    __tablename__ = "recipe_cookware"

    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), primary_key=True)
    cookware_id: Mapped[int] = mapped_column(ForeignKey("cookware.id"), primary_key=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recipe: Mapped["Recipe"] = relationship(back_populates="cookware_requirements")


class RecipeVersion(Base):
    __tablename__ = "recipe_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)


class CookingSession(Base):
    """The "one canonical current session" described in spec §1 -- never
    given a concrete table there. Added while building §6/§7's editing and
    session-lifecycle behavior, which both assume this exists. At most one
    row has status='active' at a time (enforced by a partial unique index,
    migration 0004), matching the single-session model §1 describes."""

    __tablename__ = "cooking_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")  # active | finished
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # This-time-only edits (§6) -- sparse {recipe_ingredient_id: quantity}
    # override map, cleared once committed permanent.
    ingredient_overrides: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    servings_override: Mapped[Decimal | None] = mapped_column(Numeric)


# --- Shopping & meal prep ------------------------------------------------------


class ShoppingListItem(Base):
    __tablename__ = "shopping_list"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Granularity (specific product vs. generic category) is an open item — §14.
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredients.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("ingredient_categories.id"))
    quantity_needed: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    date_added: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MealPrepBatch(Base):
    __tablename__ = "meal_prep_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    date_prepared: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    units_total: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    units_remaining: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    # Per-unit macros snapshotted at prep time (reflects any this-time-only edits active when cooked).
    macros_per_unit: Mapped[dict] = mapped_column(JSONB, nullable=False)


# --- Tracking ------------------------------------------------------------------


class MealLog(Base):
    __tablename__ = "meal_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id"))
    meal_prep_batch_id: Mapped[int | None] = mapped_column(ForeignKey("meal_prep_batches.id"))
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric)
    macros: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_estimate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Not in the original spec's field list -- added because an ad-hoc
    # estimate with no recipe/batch/ingredient link otherwise has no way to
    # record what was actually eaten.
    description: Mapped[str | None] = mapped_column(String)


class PlannedMeal(Base):
    __tablename__ = "planned_meals"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, server_default=func.current_date(), nullable=False)
    meal_slot: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    estimated_calories: Mapped[Decimal | None] = mapped_column(Numeric)
    estimated_protein_g: Mapped[Decimal | None] = mapped_column(Numeric)
    estimated_carbs_g: Mapped[Decimal | None] = mapped_column(Numeric)
    estimated_fat_g: Mapped[Decimal | None] = mapped_column(Numeric)


class WeighIn(Base):
    __tablename__ = "weigh_ins"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric, nullable=False)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    activity_type: Mapped[str | None] = mapped_column(String)
    duration_minutes: Mapped[Decimal | None] = mapped_column(Numeric)
    distance: Mapped[Decimal | None] = mapped_column(Numeric)
    calories_burned: Mapped[Decimal | None] = mapped_column(Numeric)
    # Not in the original spec's field list -- added while building the
    # Garmin sync (§9), which re-pulls overlapping date ranges and needs a
    # way to dedupe against Garmin's own activity ID rather than re-insert.
    garmin_activity_id: Mapped[str | None] = mapped_column(String, unique=True)
    # Also missing originally: Garmin's raw data includes a real start
    # time (startTimeLocal), which normalize_activity() was discarding
    # down to just a date. Added so exercises can be shown timestamped
    # alongside meals, not just bucketed by day.
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class UserGoal(Base):
    __tablename__ = "user_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    goal_type: Mapped[str | None] = mapped_column(String)
    target_deficit_surplus: Mapped[Decimal | None] = mapped_column(Numeric)
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric)
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric)
    carbs_g: Mapped[Decimal | None] = mapped_column(Numeric)
    goal_weight: Mapped[Decimal | None] = mapped_column(Numeric)
    target_date: Mapped[date | None] = mapped_column(Date)


class UserProfile(Base):
    """Singleton profile (age/sex/height), needed for the Mifflin-St Jeor
    BMR estimate behind the daily kcal deficit and expected-weight-change
    display. Not in the original spec's schema at all -- §2's TDEE
    calibration loop assumed a BMR input existed somewhere without ever
    specifying where it comes from.

    activity_level is derived fresh from a rolling window of activity_log
    on every TDEE calculation by default (see app/services/tdee.py), so a
    real change in exercise habits shows up automatically -- but
    activity_level_override lets that be pinned to an explicit value
    instead when set; null means "keep auto-deriving it"."""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    age: Mapped[int] = mapped_column(nullable=False)
    biological_sex: Mapped[str] = mapped_column(String, nullable=False)  # "male" | "female" -- Mifflin-St Jeor input
    height_cm: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    activity_level_override: Mapped[str | None] = mapped_column(String)


class RecommendationSettings(Base):
    __tablename__ = "recommendation_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    calorie_deficit_adherence: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=80)
    protein_adherence: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=80)
    carb_adherence: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=20)
    fat_adherence: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=20)
    diversity: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=50)
    expiration_urgency: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=50)
    # Named as settings in spec §8 but never given columns there -- added
    # while building the recommendation engine, which needs them.
    enabled_meal_slots: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["lunch", "dinner", "treat"]
    )
    typical_delivery_lead_hours: Mapped[int] = mapped_column(nullable=False, default=5)
    ingredient_coverage_threshold: Mapped[Decimal] = mapped_column(
        Numeric, nullable=False, default=50
    )


class UserAllergenRestriction(Base):
    """Permanent allergen exclusions (kitchen_ai_spec.md §8's "permanent
    default"). Not listed as a table in §3 -- another gap found while
    building the recommendation engine, which assumes this data exists."""

    __tablename__ = "user_allergen_restrictions"

    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)
