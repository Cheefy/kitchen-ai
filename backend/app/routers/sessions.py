from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import schemas
from app.database import get_session
from app.models import CookingSession, Recipe, RecipeIngredient, RecipeVersion
from app.services.macros import compute_recipe_macros
from app.services.sessions import (
    apply_absolute_edit,
    apply_delta_edit,
    apply_scale,
    commit_permanent,
    get_effective_ingredients,
)

router = APIRouter()


async def _load_recipe_and_session(
    session: AsyncSession, session_id: int
) -> tuple[CookingSession, Recipe]:
    cooking_session = await session.get(CookingSession, session_id)
    if cooking_session is None:
        raise HTTPException(status_code=404, detail="session not found")
    result = await session.execute(
        select(Recipe)
        .where(Recipe.id == cooking_session.recipe_id)
        .options(selectinload(Recipe.ingredients))
    )
    recipe = result.unique().scalar_one()
    return cooking_session, recipe


async def _session_response(
    session: AsyncSession, cooking_session: CookingSession, recipe: Recipe
) -> dict:
    effective = get_effective_ingredients(cooking_session, recipe.ingredients)
    macro_result = await compute_recipe_macros(session, effective)
    return {
        "id": cooking_session.id,
        "recipe_id": cooking_session.recipe_id,
        "status": cooking_session.status,
        "started_at": cooking_session.started_at,
        "ended_at": cooking_session.ended_at,
        "servings_override": cooking_session.servings_override,
        "ingredients": [
            {
                "recipe_ingredient_id": e.id,
                "category_id": e.category_id,
                "quantity": e.quantity,
                "unit": e.unit,
            }
            for e in effective
        ],
        "macros": macro_result,
    }


@router.post("/sessions/start", response_model=schemas.SessionRead)
async def start_session(
    body: schemas.SessionStart, session: AsyncSession = Depends(get_session)
):
    """kitchen_ai_spec.md §7 -- "Let's start" while a recipe's pulled up.
    Explicit and voice-triggered, not implicit; at most one active session
    at a time (DB-enforced, migration 0004)."""
    recipe = await session.get(Recipe, body.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="recipe not found")

    cooking_session = CookingSession(recipe_id=body.recipe_id)
    session.add(cooking_session)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="a cooking session is already active -- finish it first"
        ) from exc

    await session.refresh(cooking_session)
    return await _session_response(session, cooking_session, recipe)


@router.get("/sessions/active", response_model=schemas.SessionRead)
async def get_active_session(session: AsyncSession = Depends(get_session)):
    cooking_session = await session.scalar(
        select(CookingSession).where(CookingSession.status == "active")
    )
    if cooking_session is None:
        raise HTTPException(status_code=404, detail="no active session")
    _, recipe = await _load_recipe_and_session(session, cooking_session.id)
    return await _session_response(session, cooking_session, recipe)


@router.post("/sessions/{session_id}/finish", response_model=schemas.SessionRead)
async def finish_session(session_id: int, session: AsyncSession = Depends(get_session)):
    cooking_session, recipe = await _load_recipe_and_session(session, session_id)
    cooking_session.status = "finished"
    cooking_session.ended_at = func.now()
    await session.commit()
    await session.refresh(cooking_session)
    return await _session_response(session, cooking_session, recipe)


@router.patch(
    "/sessions/{session_id}/ingredients/{recipe_ingredient_id}/delta",
    response_model=schemas.SessionRead,
)
async def delta_edit(
    session_id: int,
    recipe_ingredient_id: int,
    body: schemas.DeltaEditRequest,
    session: AsyncSession = Depends(get_session),
):
    cooking_session, recipe = await _load_recipe_and_session(session, session_id)
    ri = next((r for r in recipe.ingredients if r.id == recipe_ingredient_id), None)
    if ri is None:
        raise HTTPException(status_code=404, detail="recipe_ingredient not found on this recipe")
    apply_delta_edit(cooking_session, ri, body.amount)
    await session.commit()
    await session.refresh(cooking_session)
    return await _session_response(session, cooking_session, recipe)


@router.patch(
    "/sessions/{session_id}/ingredients/{recipe_ingredient_id}/absolute",
    response_model=schemas.SessionRead,
)
async def absolute_edit(
    session_id: int,
    recipe_ingredient_id: int,
    body: schemas.AbsoluteEditRequest,
    session: AsyncSession = Depends(get_session),
):
    cooking_session, recipe = await _load_recipe_and_session(session, session_id)
    ri = next((r for r in recipe.ingredients if r.id == recipe_ingredient_id), None)
    if ri is None:
        raise HTTPException(status_code=404, detail="recipe_ingredient not found on this recipe")
    apply_absolute_edit(cooking_session, ri, body.quantity)
    await session.commit()
    await session.refresh(cooking_session)
    return await _session_response(session, cooking_session, recipe)


@router.post("/sessions/{session_id}/scale", response_model=schemas.SessionRead)
async def scale_recipe(
    session_id: int,
    body: schemas.RecipeScaleRequest,
    session: AsyncSession = Depends(get_session),
):
    cooking_session, recipe = await _load_recipe_and_session(session, session_id)

    if body.target_servings is not None:
        scale_factor = body.target_servings / recipe.base_servings
        more_servings = True
    elif body.target_recipe_ingredient_id is not None and body.target_quantity is not None:
        if body.more_servings is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "more_servings is required when scaling by an ingredient quantity -- "
                    "spec §6: 'is this still one meal, or does this make more servings?' "
                    "genuinely can't be inferred"
                ),
            )
        ri = next(
            (r for r in recipe.ingredients if r.id == body.target_recipe_ingredient_id), None
        )
        if ri is None:
            raise HTTPException(status_code=404, detail="recipe_ingredient not found")
        effective = get_effective_ingredients(cooking_session, recipe.ingredients)
        current_qty = next(e.quantity for e in effective if e.id == ri.id)
        scale_factor = body.target_quantity / current_qty
        more_servings = body.more_servings
    else:
        raise HTTPException(
            status_code=422,
            detail="provide either target_servings, or target_recipe_ingredient_id + target_quantity",
        )

    apply_scale(
        cooking_session,
        recipe,
        recipe.ingredients,
        scale_factor=scale_factor,
        more_servings=more_servings,
    )
    await session.commit()
    await session.refresh(cooking_session)
    return await _session_response(session, cooking_session, recipe)


@router.post("/sessions/{session_id}/commit-permanent", response_model=schemas.SessionRead)
async def commit_permanent_route(session_id: int, session: AsyncSession = Depends(get_session)):
    cooking_session, recipe = await _load_recipe_and_session(session, session_id)
    await commit_permanent(session, cooking_session, recipe, recipe.ingredients)
    await session.commit()
    await session.refresh(cooking_session)
    return await _session_response(session, cooking_session, recipe)


@router.get("/sessions/{session_id}/versions", response_model=list[schemas.RecipeVersionRead])
async def list_revert_options(session_id: int, session: AsyncSession = Depends(get_session)):
    """kitchen_ai_spec.md §6 -- revert always asks which change is being
    undone; this lists the candidates for that choice."""
    cooking_session, recipe = await _load_recipe_and_session(session, session_id)
    result = await session.scalars(
        select(RecipeVersion)
        .where(RecipeVersion.recipe_id == recipe.id)
        .order_by(RecipeVersion.version_number.desc())
    )
    return result.all()


@router.post("/sessions/{session_id}/revert", response_model=schemas.SessionRead)
async def revert(
    session_id: int, body: schemas.RevertRequest, session: AsyncSession = Depends(get_session)
):
    cooking_session, recipe = await _load_recipe_and_session(session, session_id)

    if body.mode == "discard_session_edits":
        cooking_session.ingredient_overrides = {}
        cooking_session.servings_override = None
        await session.commit()
        await session.refresh(cooking_session)
        return await _session_response(session, cooking_session, recipe)

    if body.mode == "restore_version":
        if body.version_id is None:
            raise HTTPException(status_code=422, detail="version_id is required for restore_version")
        target = await session.get(RecipeVersion, body.version_id)
        if target is None or target.recipe_id != recipe.id:
            raise HTTPException(status_code=404, detail="recipe version not found")

        # Log the revert itself as a new version entry first -- history
        # never has silent gaps (spec §3).
        result = await session.scalars(
            select(RecipeVersion.version_number)
            .where(RecipeVersion.recipe_id == recipe.id)
            .order_by(RecipeVersion.version_number.desc())
            .limit(1)
        )
        latest = result.first() or 0
        session.add(
            RecipeVersion(
                recipe_id=recipe.id,
                version_number=latest + 1,
                snapshot={
                    "name": recipe.name,
                    "instructions": recipe.instructions,
                    "base_servings": str(recipe.base_servings),
                    "ingredients": [
                        {"category_id": ri.category_id, "quantity": str(ri.quantity), "unit": ri.unit}
                        for ri in recipe.ingredients
                    ],
                    "reverted_to_version_id": target.id,
                },
            )
        )

        snapshot = target.snapshot
        recipe.name = snapshot.get("name", recipe.name)
        recipe.instructions = snapshot.get("instructions", recipe.instructions)
        recipe.base_servings = Decimal(snapshot.get("base_servings", str(recipe.base_servings)))

        for ri in list(recipe.ingredients):
            await session.delete(ri)
        await session.flush()
        for ing in snapshot.get("ingredients", []):
            session.add(
                RecipeIngredient(
                    recipe_id=recipe.id,
                    category_id=ing["category_id"],
                    quantity=Decimal(ing["quantity"]),
                    unit=ing["unit"],
                )
            )

        cooking_session.ingredient_overrides = {}
        cooking_session.servings_override = None
        await session.commit()

        result = await session.execute(
            select(Recipe).where(Recipe.id == recipe.id).options(selectinload(Recipe.ingredients))
        )
        recipe = result.unique().scalar_one()
        await session.refresh(cooking_session)
        return await _session_response(session, cooking_session, recipe)

    raise HTTPException(status_code=422, detail="mode must be 'discard_session_edits' or 'restore_version'")
