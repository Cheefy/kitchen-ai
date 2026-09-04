from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.database import get_session
from app.models import Ingredient, MealLog, Recipe, Unit
from app.services.macros import compute_recipe_macros
from app.services.units import ConversionNeedsInput, convert_to_canonical, to_ingredient_basis

router = APIRouter()

MACRO_FIELDS = ("calories", "protein_g", "carbs_g", "fat_g")


def _floatify(macros: dict) -> dict:
    return {k: float(v) for k, v in macros.items() if v is not None}


@router.post("/meal-log/from-recipe/{recipe_id}", response_model=schemas.MealLogRead)
async def log_recipe_eaten(
    recipe_id: int,
    body: schemas.MealLogFromRecipe,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Recipe).where(Recipe.id == recipe_id).options(selectinload(Recipe.ingredients))
    )
    recipe = result.unique().scalar_one_or_none()
    if recipe is None:
        raise HTTPException(status_code=404, detail="recipe not found")

    macro_result = await compute_recipe_macros(session, recipe.ingredients)
    if not macro_result["fully_resolved"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "recipe's macros can't be fully resolved from current inventory yet",
                "resolution": macro_result["ingredients"],
            },
        )

    ratio = body.servings / recipe.base_servings
    scaled = {k: v * ratio for k, v in macro_result["totals"].items()}

    entry = MealLog(
        recipe_id=recipe_id,
        quantity=body.servings,
        macros=_floatify(scaled),
        is_estimate=False,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.post("/meal-log/from-ingredient", response_model=schemas.MealLogRead)
async def log_ingredient_eaten(
    body: schemas.MealLogFromIngredient, session: AsyncSession = Depends(get_session)
):
    ingredient = await session.get(Ingredient, body.ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="ingredient not found")
    unit = await session.get(Unit, body.unit)
    if unit is None:
        raise HTTPException(status_code=404, detail=f"unknown unit code: {body.unit!r}")

    try:
        canonical_qty, canonical_unit = convert_to_canonical(body.quantity, unit, ingredient)
        basis_qty = to_ingredient_basis(canonical_qty, canonical_unit, ingredient)
    except ConversionNeedsInput as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "ingredient_id": ingredient.id,
                "needs_field": exc.field,
                "resolve_via": f"PATCH /ingredients/{ingredient.id}/tier2",
            },
        ) from exc

    if not ingredient.serving_size:
        raise HTTPException(
            status_code=409, detail=f"'{ingredient.name}' has no serving_size/macro data set"
        )

    scale = basis_qty / ingredient.serving_size
    macros = {
        field: getattr(ingredient, field) * scale
        for field in MACRO_FIELDS
        if getattr(ingredient, field) is not None
    }

    entry = MealLog(
        ingredient_id=body.ingredient_id,
        quantity=body.quantity,
        macros=_floatify(macros),
        is_estimate=(ingredient.source == "estimate"),
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.post("/meal-log/estimate", response_model=schemas.MealLogRead)
async def log_estimate(
    body: schemas.MealLogEstimate, session: AsyncSession = Depends(get_session)
):
    """kitchen_ai_spec.md §7 -- a rough estimate, logged for this meal only.
    No permanent `ingredients` row is created."""
    macros = {f: getattr(body, f) for f in MACRO_FIELDS if getattr(body, f) is not None}
    entry = MealLog(
        description=body.description, macros=_floatify(macros), is_estimate=True
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.get("/meal-log", response_model=list[schemas.MealLogRead])
async def list_meal_log(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(MealLog).order_by(MealLog.timestamp.desc()))
    return result.all()


@router.patch("/meal-log/{entry_id}", response_model=schemas.MealLogRead)
async def update_meal_log(
    entry_id: int, body: schemas.MealLogUpdate, session: AsyncSession = Depends(get_session)
):
    entry = await session.get(MealLog, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="meal log entry not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "macros" and value is not None:
            setattr(entry, field, _floatify(value))
        else:
            setattr(entry, field, value)

    await session.commit()
    await session.refresh(entry)
    return entry


@router.delete("/meal-log/{entry_id}", status_code=204)
async def delete_meal_log(entry_id: int, session: AsyncSession = Depends(get_session)):
    entry = await session.get(MealLog, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="meal log entry not found")
    await session.delete(entry)
    await session.commit()
