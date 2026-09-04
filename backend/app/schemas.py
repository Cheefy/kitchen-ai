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
