from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import Ingredient, IngredientCategory
from app.services.logging import log_assumption

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


@router.get("/ingredients/{ingredient_id}", response_model=schemas.IngredientRead)
async def get_ingredient(ingredient_id: int, session: AsyncSession = Depends(get_session)):
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="ingredient not found")
    return ingredient


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
