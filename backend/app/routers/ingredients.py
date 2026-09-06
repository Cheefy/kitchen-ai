from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import Ingredient, IngredientCategory
from app.services.logging import log_assumption
from app.services.nutrition_lookup import lookup_barcode_external, search_nutrition_by_name

router = APIRouter()


@router.post("/categories", response_model=schemas.CategoryRead)
async def create_category(
    body: schemas.CategoryCreate, session: AsyncSession = Depends(get_session)
):
    existing = await session.scalar(
        select(IngredientCategory).where(IngredientCategory.name == body.name)
    )
    if existing:
        return existing
    category = IngredientCategory(name=body.name)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


@router.get("/categories", response_model=list[schemas.CategoryRead])
async def list_categories(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(IngredientCategory).order_by(IngredientCategory.name))
    return result.all()


@router.post("/ingredients", response_model=schemas.IngredientRead)
async def create_ingredient(
    body: schemas.IngredientCreate, session: AsyncSession = Depends(get_session)
):
    category = await session.get(IngredientCategory, body.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="category_id does not exist")

    ingredient = Ingredient(**body.model_dump())
    session.add(ingredient)
    await session.commit()
    await session.refresh(ingredient)
    return ingredient


@router.get("/ingredients", response_model=list[schemas.IngredientRead])
async def list_ingredients(
    q: str | None = None, session: AsyncSession = Depends(get_session)
):
    stmt = select(Ingredient).order_by(Ingredient.name)
    if q:
        stmt = stmt.where(Ingredient.name.ilike(f"%{q}%"))
    result = await session.scalars(stmt)
    return result.all()


@router.get("/ingredients/barcode/{upc}", response_model=schemas.IngredientRead)
async def lookup_by_barcode(upc: str, session: AsyncSession = Depends(get_session)):
    """kitchen_ai_spec.md §4 step 1 -- matched vs. not-matched drives the
    ingestion flow client-side (a 404 here means "scan the label instead")."""
    ingredient = await session.scalar(
        select(Ingredient).where(Ingredient.upc_barcode == upc)
    )
    if ingredient is None:
        raise HTTPException(status_code=404, detail="no ingredient matches this barcode")
    return ingredient


@router.get("/ingredients/barcode/{upc}/external", response_model=schemas.NutritionCandidate)
async def lookup_by_barcode_external(upc: str):
    """Not in our own DB (the 404 above) -- try Open Food Facts before
    falling back to manual entry. Preview only, nothing persisted yet."""
    result = await lookup_barcode_external(upc)
    if result is None:
        raise HTTPException(status_code=404, detail="no product found for this barcode externally either")
    return result


@router.post("/ingredients/from-barcode", response_model=schemas.IngredientRead)
async def create_ingredient_from_barcode(
    body: schemas.IngredientFromBarcode, session: AsyncSession = Depends(get_session)
):
    """Persists an Open Food Facts lookup as a real Ingredient, after the
    user's reviewed the preview from the /external route above."""
    category = await session.get(IngredientCategory, body.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="category_id does not exist")

    existing = await session.scalar(select(Ingredient).where(Ingredient.upc_barcode == body.upc))
    if existing is not None:
        return existing

    looked_up = await lookup_barcode_external(body.upc)
    if looked_up is None:
        raise HTTPException(status_code=404, detail="no product found for this barcode externally either")

    ingredient = Ingredient(category_id=body.category_id, **looked_up)
    session.add(ingredient)
    await session.commit()
    await session.refresh(ingredient)
    return ingredient


@router.get("/ingredients/nutrition-search", response_model=list[schemas.NutritionCandidate])
async def nutrition_search(q: str):
    """USDA FoodData Central search-by-name, for ingredients that don't
    have a barcode (fresh produce, bulk bins) -- lets the add-ingredient
    form autofill macros instead of the user typing them from a label."""
    return await search_nutrition_by_name(q)


@router.get("/ingredients/{ingredient_id}", response_model=schemas.IngredientRead)
async def get_ingredient(ingredient_id: int, session: AsyncSession = Depends(get_session)):
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="ingredient not found")
    return ingredient


@router.patch("/ingredients/{ingredient_id}/tier2", response_model=schemas.IngredientRead)
async def backfill_tier2(
    ingredient_id: int,
    body: schemas.IngredientTierTwoUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Backfills density_g_per_ml / unit_weight_g once the one-time
    clarifying question (kitchen_ai_spec.md §5) has been answered."""
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="ingredient not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ingredient, field, value)

    await log_assumption(
        session,
        behavior_key="unit_conversion_tier2",
        description=f"Recorded unit-conversion data for '{ingredient.name}'",
        trigger="user answered one-time density/unit-weight question",
    )
    await session.commit()
    await session.refresh(ingredient)
    return ingredient
