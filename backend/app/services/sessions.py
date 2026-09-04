"""Recipe modification & scaling within a cooking session (kitchen_ai_spec.md
§6). Edits always land on the session-scoped copy (`ingredient_overrides`)
first -- this-time-only by default, per the assume-and-announce tier of the
Guiding Principle. Only commit_permanent() ever touches the live recipe.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CookingSession, Recipe, RecipeIngredient, RecipeVersion


@dataclass
class EffectiveIngredient:
    """A RecipeIngredient with any session override applied. Duck-types the
    fields compute_recipe_macros() actually reads."""

    id: int
    category_id: int
    quantity: Decimal
    unit: str


def get_effective_ingredients(
    cooking_session: CookingSession, recipe_ingredients: list[RecipeIngredient]
) -> list[EffectiveIngredient]:
    overrides = cooking_session.ingredient_overrides or {}
    return [
        EffectiveIngredient(
            id=ri.id,
            category_id=ri.category_id,
            quantity=Decimal(str(overrides[str(ri.id)])) if str(ri.id) in overrides else ri.quantity,
            unit=ri.unit,
        )
        for ri in recipe_ingredients
    ]


def apply_delta_edit(
    cooking_session: CookingSession, recipe_ingredient: RecipeIngredient, delta: Decimal
) -> Decimal:
    """'2g more/less garlic' -- signed delta against the *current* (possibly
    already session-modified) quantity for that one ingredient only."""
    overrides = dict(cooking_session.ingredient_overrides or {})
    current = (
        Decimal(str(overrides[str(recipe_ingredient.id)]))
        if str(recipe_ingredient.id) in overrides
        else recipe_ingredient.quantity
    )
    new_qty = current + delta
    overrides[str(recipe_ingredient.id)] = str(new_qty)
    cooking_session.ingredient_overrides = overrides
    return new_qty


def apply_absolute_edit(
    cooking_session: CookingSession, recipe_ingredient: RecipeIngredient, new_qty: Decimal
) -> Decimal:
    """'change/set/use chicken to 180g' -- overwrites that one ingredient's
    quantity only. Nothing else in the recipe moves."""
    overrides = dict(cooking_session.ingredient_overrides or {})
    overrides[str(recipe_ingredient.id)] = str(new_qty)
    cooking_session.ingredient_overrides = overrides
    return new_qty


def apply_scale(
    cooking_session: CookingSession,
    recipe: Recipe,
    recipe_ingredients: list[RecipeIngredient],
    *,
    scale_factor: Decimal,
    more_servings: bool,
) -> None:
    """Proportional scale, applied to every ingredient. `more_servings`
    distinguishes "still one meal" (quantities scale, servings fixed) from
    "more servings" (quantities and servings scale together) -- this can't
    be inferred, so the caller (not this function) is responsible for
    having actually asked."""
    overrides = dict(cooking_session.ingredient_overrides or {})
    for ri in recipe_ingredients:
        current = (
            Decimal(str(overrides[str(ri.id)])) if str(ri.id) in overrides else ri.quantity
        )
        overrides[str(ri.id)] = str(current * scale_factor)
    cooking_session.ingredient_overrides = overrides
    if more_servings:
        cooking_session.servings_override = recipe.base_servings * scale_factor


async def commit_permanent(session: AsyncSession, cooking_session: CookingSession, recipe: Recipe, recipe_ingredients: list[RecipeIngredient]) -> RecipeVersion:
    """Writes the pre-change snapshot, then mutates the live recipe with
    whatever's currently session-scoped, and clears the session overrides
    since they're no longer "this session only" (kitchen_ai_spec.md §3/§6)."""
    next_version = (
        await session.scalar(
            select(func.coalesce(func.max(RecipeVersion.version_number), 0)).where(
                RecipeVersion.recipe_id == recipe.id
            )
        )
    ) + 1

    pre_change_snapshot = RecipeVersion(
        recipe_id=recipe.id,
        version_number=next_version,
        snapshot={
            "name": recipe.name,
            "instructions": recipe.instructions,
            "base_servings": str(recipe.base_servings),
            "ingredients": [
                {"category_id": ri.category_id, "quantity": str(ri.quantity), "unit": ri.unit}
                for ri in recipe_ingredients
            ],
        },
    )
    session.add(pre_change_snapshot)

    overrides = cooking_session.ingredient_overrides or {}
    for ri in recipe_ingredients:
        if str(ri.id) in overrides:
            ri.quantity = Decimal(str(overrides[str(ri.id)]))
    if cooking_session.servings_override is not None:
        recipe.base_servings = cooking_session.servings_override

    cooking_session.ingredient_overrides = {}
    cooking_session.servings_override = None

    await session.flush()
    return pre_change_snapshot
