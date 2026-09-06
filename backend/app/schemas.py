from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class AllergenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class IngredientCreate(BaseModel):
    name: str
    upc_barcode: str | None = None
    category_id: int
    calories: Decimal | None = None
    protein_g: Decimal | None = None
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None
    serving_size: Decimal | None = None
    serving_size_unit: str = "g"
    saturated_fat_g: Decimal | None = None
    sodium_mg: Decimal | None = None
    fiber_g: Decimal | None = None
    sugars_g: Decimal | None = None
    micronutrients: dict | None = None
    ingredients_list_raw: str | None = None
    source: str
    density_g_per_ml: Decimal | None = None
    unit_weight_g: Decimal | None = None
    unit_label: str | None = None


class IngredientRead(IngredientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class IngredientTierTwoUpdate(BaseModel):
    """Backfills the volume/count -> mass bridge once the user answers the
    one-time clarifying question (kitchen_ai_spec.md §5)."""

    density_g_per_ml: Decimal | None = None
    unit_weight_g: Decimal | None = None
    unit_label: str | None = None


class InventoryItemCreate(BaseModel):
    ingredient_id: int
    quantity: Decimal
    unit: str
    expiration_date: date | None = None
    location: str | None = None


class InventoryItemUpdate(BaseModel):
    quantity: Decimal | None = None
    expiration_date: date | None = None
    location: str | None = None


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ingredient_id: int
    quantity: Decimal
    unit: str
    expiration_date: date | None
    location: str | None


class CookwareCreate(BaseModel):
    name: str
    type: str | None = None
    tare_weight: Decimal | None = None
    label_number: str | None = None


class CookwareRead(CookwareCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RecipeIngredientIn(BaseModel):
    category_id: int
    quantity: Decimal
    unit: str


class RecipeIngredientRead(RecipeIngredientIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RecipeCookwareIn(BaseModel):
    cookware_id: int
    required: bool = True


class RecipeCookwareRead(RecipeCookwareIn):
    model_config = ConfigDict(from_attributes=True)


class RecipeCreate(BaseModel):
    name: str
    instructions: str | None = None
    base_servings: Decimal
    prep_minutes: int | None = None
    active_minutes: int | None = None
    passive_minutes: int | None = None
    ingredients: list[RecipeIngredientIn] = []
    cookware: list[RecipeCookwareIn] = []


class RecipeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    instructions: str | None
    base_servings: Decimal
    prep_minutes: int | None
    active_minutes: int | None
    passive_minutes: int | None
    ingredients: list[RecipeIngredientRead]
    cookware_requirements: list[RecipeCookwareRead]


class RecipeIngredientMacroLine(BaseModel):
    recipe_ingredient_id: int
    category_id: int
    resolution: str
    ingredient_id: int | None = None
    ingredient_name: str | None = None
    candidate_ingredient_ids: list[int] | None = None
    error: str | None = None
    scale: Decimal | None = None


class RecipeMacros(BaseModel):
    fully_resolved: bool
    totals: dict[str, Decimal]
    ingredients: list[RecipeIngredientMacroLine]


class ActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    activity_type: str | None
    duration_minutes: Decimal | None
    distance: Decimal | None
    calories_burned: Decimal | None
    garmin_activity_id: str | None


class GarminSyncResult(BaseModel):
    fetched: int
    added: int
    skipped_duplicates: int


class NotificationTestRequest(BaseModel):
    message: str = "Test notification from Kitchen AI"


class DownscaleSuggestion(BaseModel):
    recipe_id: int
    sample_size: int
    average_eaten_fraction: Decimal
    suggested_scale_factor: Decimal


class SessionStart(BaseModel):
    recipe_id: int


class EffectiveIngredientRead(BaseModel):
    recipe_ingredient_id: int
    category_id: int
    quantity: Decimal
    unit: str


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    status: str
    started_at: datetime
    ended_at: datetime | None
    servings_override: Decimal | None
    ingredients: list[EffectiveIngredientRead]
    macros: RecipeMacros


class DeltaEditRequest(BaseModel):
    amount: Decimal  # signed -- negative for "less"


class AbsoluteEditRequest(BaseModel):
    quantity: Decimal


class RecipeScaleRequest(BaseModel):
    """Provide exactly one of target_servings or
    (target_recipe_ingredient_id + target_quantity). Scaling by an
    ingredient quantity requires more_servings -- per spec §6 this
    genuinely can't be inferred, so it's a required field rather than a
    default; omitting it represents the "must ask" case as a 422."""

    target_servings: Decimal | None = None
    target_recipe_ingredient_id: int | None = None
    target_quantity: Decimal | None = None
    more_servings: bool | None = None


class RevertRequest(BaseModel):
    mode: str  # "discard_session_edits" | "restore_version"
    version_id: int | None = None


class RecipeVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    version_number: int
    changed_at: datetime
    snapshot: dict


class RecipeCandidate(BaseModel):
    recipe_id: int
    name: str
    macros: dict[str, Decimal]
    ingredient_ids: list[int]


class ExcludedRecipe(BaseModel):
    recipe_id: int
    name: str
    reason: str
    missing_cookware_ids: list[int] | None = None
    detail: list[dict] | None = None


class ExpiringUnusedIngredient(BaseModel):
    inventory_id: int
    ingredient_id: int
    expiration_date: date


class Recommendations(BaseModel):
    full_stock: list[RecipeCandidate]
    shopping_required: list[RecipeCandidate]
    excluded: list[ExcludedRecipe]
    expiring_unused_ingredients: list[ExpiringUnusedIngredient]


class AllergenRestrictionCreate(BaseModel):
    allergen_id: int


class UserProfileUpdate(BaseModel):
    age: int | None = None
    biological_sex: str | None = None  # "male" | "female"
    height_cm: Decimal | None = None
    activity_level_override: str | None = None  # null clears it, "" is not accepted


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    age: int
    biological_sex: str
    height_cm: Decimal
    activity_level_override: str | None


class TdeeRead(BaseModel):
    bmr: Decimal
    activity_level: str
    activity_level_is_override: bool
    sessions_per_week: Decimal | None
    tdee: Decimal
    calibrating: bool


class DailyTargetsRead(BaseModel):
    bmr: Decimal
    tdee: Decimal
    activity_level: str
    activity_level_is_override: bool
    sessions_per_week: Decimal | None
    calibrating: bool
    calorie_target: Decimal
    deficit_applied: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbs_g: Decimal


class CalendarMealEntry(BaseModel):
    id: int
    timestamp: datetime
    label: str
    calories: Decimal | None
    is_estimate: bool


class CalendarExerciseEntry(BaseModel):
    id: int
    timestamp: datetime | None
    activity_type: str | None
    duration_minutes: Decimal | None
    distance: Decimal | None
    calories_burned: Decimal | None


class CalendarDay(BaseModel):
    date: date
    meals: list[CalendarMealEntry]
    exercises: list[CalendarExerciseEntry]
    calories_eaten: Decimal
    calories_burned_exercise: Decimal
    tdee: Decimal | None
    deficit: Decimal | None
    expected_weight_change_lb: Decimal | None
    calibrating: bool
    note: str | None = None


class CalendarResponse(BaseModel):
    days: list[CalendarDay]


class WeighInCreate(BaseModel):
    date: date
    weight: Decimal


class WeighInRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    weight: Decimal


class UserGoalCreate(BaseModel):
    effective_date: date
    goal_type: str | None = None
    protein_g: Decimal | None = None
    fat_g: Decimal | None = None
    carbs_g: Decimal | None = None
    goal_weight: Decimal
    target_deficit_surplus: Decimal | None = None
    target_date: date | None = None


class UserGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    effective_date: date
    goal_type: str | None
    target_deficit_surplus: Decimal | None
    protein_g: Decimal | None
    fat_g: Decimal | None
    carbs_g: Decimal | None
    goal_weight: Decimal | None
    target_date: date | None


class RecommendationSettingsUpdate(BaseModel):
    calorie_deficit_adherence: Decimal | None = None
    protein_adherence: Decimal | None = None
    carb_adherence: Decimal | None = None
    fat_adherence: Decimal | None = None
    diversity: Decimal | None = None
    expiration_urgency: Decimal | None = None


class RecommendationSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    calorie_deficit_adherence: Decimal
    protein_adherence: Decimal
    carb_adherence: Decimal
    fat_adherence: Decimal
    diversity: Decimal
    expiration_urgency: Decimal


class PlannedMealCreate(BaseModel):
    meal_slot: str
    description: str | None = None
    estimated_calories: Decimal | None = None
    estimated_protein_g: Decimal | None = None
    estimated_carbs_g: Decimal | None = None
    estimated_fat_g: Decimal | None = None


class PlannedMealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    meal_slot: str
    description: str | None
    estimated_calories: Decimal | None
    estimated_protein_g: Decimal | None
    estimated_carbs_g: Decimal | None
    estimated_fat_g: Decimal | None


class DeductionLine(BaseModel):
    ingredient_id: int
    ingredient_name: str
    deducted: Decimal
    unit: str


class MealPrepBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    description: str | None
    date_prepared: datetime
    units_total: Decimal
    units_remaining: Decimal
    macros_per_unit: dict


class FinishCookingRequest(BaseModel):
    """kitchen_ai_spec.md §7 -- "deduct the ingredients and count as eaten"
    is a compound command; deduct_and_eaten does both as separable actions
    from one call. percent_eaten defaults to 100 -- "I'm finished cooking"
    alone defaults to the whole recipe eaten, stated, correctable after."""

    mode: str  # "deduct_only" | "deduct_and_eaten"
    percent_eaten: Decimal = Decimal("100")


class EatBatchRequest(BaseModel):
    percent: Decimal = Decimal("100")


class DisposeBatchRequest(BaseModel):
    percent: Decimal = Decimal("100")


class MealLogFromRecipe(BaseModel):
    servings: Decimal = Decimal("1")


class MealLogFromIngredient(BaseModel):
    ingredient_id: int
    quantity: Decimal
    unit: str


class MealLogEstimate(BaseModel):
    description: str
    calories: Decimal | None = None
    protein_g: Decimal | None = None
    carbs_g: Decimal | None = None
    fat_g: Decimal | None = None


class MealLogUpdate(BaseModel):
    """Simple field edits only. The full is_estimate-toggle-driven
    promote/propagate-to-ingredients behavior from spec §7 is more involved
    (reverse-scaling macros onto a per-serving basis) and is deferred to
    its own pass rather than half-implemented here."""

    macros: dict[str, Decimal] | None = None
    quantity: Decimal | None = None
    is_estimate: bool | None = None


class ShoppingListItemCreate(BaseModel):
    ingredient_id: int | None = None
    category_id: int | None = None
    quantity_needed: Decimal


class ShoppingListItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ingredient_id: int | None
    category_id: int | None
    quantity_needed: Decimal
    date_added: datetime


class BehaviorSettingUpsert(BaseModel):
    mode: str  # "assume_and_announce" | "always_ask"


class BehaviorSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    mode: str


class SystemLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    description: str
    trigger: str | None
    corrected: bool
    behavior_key: str | None


class MealLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    recipe_id: int | None
    meal_prep_batch_id: int | None
    ingredient_id: int | None
    quantity: Decimal | None
    description: str | None
    macros: dict
    is_estimate: bool


class FinishCookingResult(BaseModel):
    batch: MealPrepBatchRead
    deductions: list[DeductionLine]
    meal_log_entry: MealLogRead | None = None


class SettingsExport(BaseModel):
    """A local backup file for the app-level preferences you'd otherwise
    have to re-enter through Settings: profile, recommendation sliders,
    behavior toggles, allergen restrictions. Deliberately excludes goals
    (a dated history, not a "preference") and anything tied to a moment
    in time (weigh-ins, meal/activity logs)."""

    exported_at: datetime
    profile: UserProfileRead | None
    recommendation_settings: RecommendationSettingsRead
    behavior_settings: list[BehaviorSettingRead]
    allergen_restrictions: list[AllergenRead]


class SettingsImportResult(BaseModel):
    profile_restored: bool
    recommendation_settings_restored: bool
    behavior_settings_restored: int
    allergen_restrictions_restored: int


class VoiceCommandRequest(BaseModel):
    transcript: str


class VoiceToolCallLog(BaseModel):
    name: str
    arguments: dict
    result: dict


class VoiceCommandResult(BaseModel):
    reply: str
    tool_calls: list[VoiceToolCallLog]
