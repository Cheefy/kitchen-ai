from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.database import get_session
from app.models import CookingSession, MealLog, MealPrepBatch, Recipe
from app.services.deduction import (
    InsufficientStock,
    MixedUnitInventory,
    UnresolvedIngredient,
    deduct_session_ingredients,
)
from app.services.macros import compute_recipe_macros, floatify_macros
from app.services.sessions import get_effective_ingredients

router = APIRouter()


@router.post("/sessions/{session_id}/finish-cooking", response_model=schemas.FinishCookingResult)
async def finish_cooking(
    session_id: int,
    body: schemas.FinishCookingRequest,
    session: AsyncSession = Depends(get_session),
):
    """kitchen_ai_spec.md §7 -- the compound command. Deducts inventory
    always; deduct_and_eaten also logs it eaten, as two separable actions
    from one call (deduct_only alone leaves a pending meal_prep_batches
    row, per spec)."""
    cooking_session = await session.get(CookingSession, session_id)
    if cooking_session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if cooking_session.status != "active":
        raise HTTPException(status_code=409, detail="session is not active")
    if body.mode not in ("deduct_only", "deduct_and_eaten"):
        raise HTTPException(status_code=422, detail="mode must be 'deduct_only' or 'deduct_and_eaten'")

    result = await session.execute(
        select(Recipe)
        .where(Recipe.id == cooking_session.recipe_id)
        .options(selectinload(Recipe.ingredients))
    )
    recipe = result.unique().scalar_one()
    effective = get_effective_ingredients(cooking_session, recipe.ingredients)

    macro_result = await compute_recipe_macros(session, effective)
    if not macro_result["fully_resolved"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "recipe's macros can't be fully resolved from current inventory yet",
                "resolution": macro_result["ingredients"],
            },
        )

    try:
        deductions = await deduct_session_ingredients(session, effective)
    except (InsufficientStock, UnresolvedIngredient, MixedUnitInventory) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    servings = cooking_session.servings_override or recipe.base_servings
    macros_per_unit = {k: v / servings for k, v in macro_result["totals"].items()}

    batch = MealPrepBatch(
        recipe_id=recipe.id,
        units_total=Decimal("1"),
        units_remaining=Decimal("1"),
        macros_per_unit=floatify_macros(macros_per_unit),
    )
    session.add(batch)
    await session.flush()

    meal_log_entry = None
    if body.mode == "deduct_and_eaten":
        # "I'm finished cooking" alone defaults to 100% eaten, stated
        # plainly and correctable after -- percent_eaten's own default.
        fraction = body.percent_eaten / Decimal("100")
        eaten_macros = {k: v * fraction for k, v in macros_per_unit.items()}
        meal_log_entry = MealLog(
            meal_prep_batch_id=batch.id,
            quantity=fraction,
            macros=floatify_macros(eaten_macros),
            is_estimate=False,
        )
        session.add(meal_log_entry)
        batch.units_remaining = batch.units_remaining - fraction

    cooking_session.status = "finished"
    cooking_session.ended_at = func.now()

    await session.commit()
    await session.refresh(batch)
    if meal_log_entry is not None:
        await session.refresh(meal_log_entry)

    return {"batch": batch, "deductions": deductions, "meal_log_entry": meal_log_entry}


@router.get("/meal-prep-batches", response_model=list[schemas.MealPrepBatchRead])
async def list_batches(
    pending_only: bool = False, session: AsyncSession = Depends(get_session)
):
    stmt = select(MealPrepBatch).order_by(MealPrepBatch.date_prepared.desc())
    if pending_only:
        stmt = stmt.where(MealPrepBatch.units_remaining > 0)
    result = await session.scalars(stmt)
    return result.all()


@router.get("/meal-prep-batches/{batch_id}", response_model=schemas.MealPrepBatchRead)
async def get_batch(batch_id: int, session: AsyncSession = Depends(get_session)):
    batch = await session.get(MealPrepBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return batch


@router.post("/meal-prep-batches/{batch_id}/eat", response_model=schemas.MealLogRead)
async def eat_batch(
    batch_id: int, body: schemas.EatBatchRequest, session: AsyncSession = Depends(get_session)
):
    """kitchen_ai_spec.md §3 -- decrements units_remaining, writes a
    meal_log entry from the snapshotted per-unit macros. Supports partial
    consumption (e.g. percent=60 -> units_remaining drops by 0.6),
    chaining correctly across repeated calls since each is a further
    subtraction from whatever fraction remains."""
    batch = await session.get(MealPrepBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")

    fraction = body.percent / Decimal("100")
    if fraction > batch.units_remaining:
        raise HTTPException(
            status_code=409,
            detail=f"only {batch.units_remaining * 100}% remains -- can't eat {body.percent}%",
        )

    macros = {k: Decimal(str(v)) * fraction for k, v in batch.macros_per_unit.items()}
    entry = MealLog(
        meal_prep_batch_id=batch.id,
        quantity=fraction,
        macros=floatify_macros(macros),
        is_estimate=False,
    )
    session.add(entry)
    batch.units_remaining -= fraction
    await session.commit()
    await session.refresh(entry)
    return entry


@router.post("/meal-prep-batches/{batch_id}/dispose", status_code=204)
async def dispose_batch(
    batch_id: int, body: schemas.DisposeBatchRequest, session: AsyncSession = Depends(get_session)
):
    """kitchen_ai_spec.md §3 -- decrements units_remaining, NO meal_log
    entry (disposing isn't eating)."""
    batch = await session.get(MealPrepBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")

    fraction = body.percent / Decimal("100")
    if fraction > batch.units_remaining:
        raise HTTPException(
            status_code=409,
            detail=f"only {batch.units_remaining * 100}% remains -- can't dispose {body.percent}%",
        )
    batch.units_remaining -= fraction
    await session.commit()
