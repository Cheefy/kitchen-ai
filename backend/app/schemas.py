from datetime import date
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
