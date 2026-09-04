from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.database import get_session
from app.models import (
    Cookware,
    IngredientCategory,
    Recipe,
    RecipeCookware,
    RecipeIngredient,
    RecipeVersion,
)
from app.services.macros import compute_recipe_macros

router = APIRouter()


def _recipe_load_options():
    return (selectinload(Recipe.ingredients), selectinload(Recipe.cookware_requirements))


@router.post("/recipes", response_model=schemas.RecipeRead)
async def create_recipe(
    body: schemas.RecipeCreate, session: AsyncSession = Depends(get_session)
):
    for ri in body.ingredients:
        if await session.get(IngredientCategory, ri.category_id) is None:
            raise HTTPException(
                status_code=404, detail=f"category_id {ri.category_id} does not exist"
            )
    for rc in body.cookware:
        if await session.get(Cookware, rc.cookware_id) is None:
            raise HTTPException(
                status_code=404, detail=f"cookware_id {rc.cookware_id} does not exist"
            )

    recipe = Recipe(
        name=body.name,
        instructions=body.instructions,
        base_servings=body.base_servings,
        prep_minutes=body.prep_minutes,
        active_minutes=body.active_minutes,
        passive_minutes=body.passive_minutes,
        ingredients=[
            RecipeIngredient(category_id=ri.category_id, quantity=ri.quantity, unit=ri.unit)
            for ri in body.ingredients
        ],
        cookware_requirements=[
            RecipeCookware(cookware_id=rc.cookware_id, required=rc.required)
            for rc in body.cookware
        ],
    )
    session.add(recipe)
    await session.flush()  # assigns recipe.id

    # kitchen_ai_spec.md §3: recipe_versions holds a full snapshot, not a
    # diff -- version 1 is written at creation, same as any later edit.
    session.add(
        RecipeVersion(
            recipe_id=recipe.id,
            version_number=1,
            snapshot={
                "name": recipe.name,
                "instructions": recipe.instructions,
                "base_servings": str(recipe.base_servings),
                "ingredients": [
                    {"category_id": ri.category_id, "quantity": str(ri.quantity), "unit": ri.unit}
                    for ri in body.ingredients
                ],
            },
        )
    )

    await session.commit()

    result = await session.execute(
        select(Recipe).where(Recipe.id == recipe.id).options(*_recipe_load_options())
    )
    return result.unique().scalar_one()


@router.get("/recipes", response_model=list[schemas.RecipeRead])
async def list_recipes(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Recipe).options(*_recipe_load_options()).order_by(Recipe.name)
    )
    return result.unique().scalars().all()


@router.get("/recipes/{recipe_id}", response_model=schemas.RecipeRead)
async def get_recipe(recipe_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Recipe).where(Recipe.id == recipe_id).options(*_recipe_load_options())
    )
    recipe = result.unique().scalar_one_or_none()
    if recipe is None:
        raise HTTPException(status_code=404, detail="recipe not found")
    return recipe


@router.get("/recipes/{recipe_id}/macros", response_model=schemas.RecipeMacros)
async def get_recipe_macros(recipe_id: int, session: AsyncSession = Depends(get_session)):
    """Live macro computation, kitchen_ai_spec.md §3 -- never cached,
    always recomputed from current inventory via §4 resolution."""
    result = await session.execute(
        select(Recipe).where(Recipe.id == recipe_id).options(selectinload(Recipe.ingredients))
    )
    recipe = result.unique().scalar_one_or_none()
    if recipe is None:
        raise HTTPException(status_code=404, detail="recipe not found")
    return await compute_recipe_macros(session, recipe.ingredients)
