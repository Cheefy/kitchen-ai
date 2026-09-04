"""Recipe recommendation engine (kitchen_ai_spec.md §8). Scope for this
pass: hard filters (time, cookware, allergens) plus full-stock/shopping-
required tiering, built on the resolution/macro machinery already in
place. Deliberately deferred: slider-weighted ranking within each tier
(needs a daily calorie target, which needs TDEE/BMR calibration -- an
explicitly multi-week process per §2, not something to fake here),
diversity scoring against meal_log history, session-declared allergen
exceptions (needs session-state infra, §14), forward-looking/delivery-
order mode, and phrasing the expiring-ingredient side-dish suggestion
(that's the LLM layer's job -- this only surfaces the structured signal).
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Cookware, IngredientAllergen, InventoryItem, Recipe, UserAllergenRestriction
from app.services.macros import compute_recipe_macros


async def _restricted_allergen_ids(session: AsyncSession) -> set[int]:
    result = await session.scalars(select(UserAllergenRestriction.allergen_id))
    return set(result.all())


async def get_recommendations(session: AsyncSession, *, max_minutes: int | None = None) -> dict:
    restricted_ids = await _restricted_allergen_ids(session)

    result = await session.execute(
        select(Recipe).options(
            selectinload(Recipe.ingredients), selectinload(Recipe.cookware_requirements)
        )
    )
    recipes = result.unique().scalars().all()

    full_stock, shopping_required, excluded = [], [], []

    for recipe in recipes:
        # Hard filter: time (prep + active only -- passive/unattended time
        # doesn't block "can I fit this", per §8).
        if max_minutes is not None:
            active_time = (recipe.prep_minutes or 0) + (recipe.active_minutes or 0)
            if active_time > max_minutes:
                excluded.append(
                    {"recipe_id": recipe.id, "name": recipe.name, "reason": "time_constraint"}
                )
                continue

        # Hard filter: cookware available.
        missing_cookware = [
            rc.cookware_id
            for rc in recipe.cookware_requirements
            if rc.required and await session.get(Cookware, rc.cookware_id) is None
        ]
        if missing_cookware:
            excluded.append(
                {
                    "recipe_id": recipe.id,
                    "name": recipe.name,
                    "reason": "cookware_unavailable",
                    "missing_cookware_ids": missing_cookware,
                }
            )
            continue

        macro_result = await compute_recipe_macros(session, recipe.ingredients)
        resolved_ids = [
            line["ingredient_id"] for line in macro_result["ingredients"] if line.get("ingredient_id")
        ]

        # Hard filter: allergens, checked against whatever ingredients
        # actually resolved (a recipe only names a generic category).
        if restricted_ids and resolved_ids:
            stmt = select(IngredientAllergen.ingredient_id).where(
                IngredientAllergen.ingredient_id.in_(resolved_ids),
                IngredientAllergen.allergen_id.in_(restricted_ids),
            )
            if await session.scalar(stmt) is not None:
                excluded.append(
                    {"recipe_id": recipe.id, "name": recipe.name, "reason": "allergen_restricted"}
                )
                continue

        candidate = {
            "recipe_id": recipe.id,
            "name": recipe.name,
            "macros": macro_result["totals"],
            "ingredient_ids": resolved_ids,
        }

        if macro_result["fully_resolved"]:
            full_stock.append(candidate)
        elif any(line["resolution"] == "needs_shopping" for line in macro_result["ingredients"]):
            shopping_required.append(candidate)
        else:
            excluded.append(
                {
                    "recipe_id": recipe.id,
                    "name": recipe.name,
                    "reason": "needs_clarification",
                    "detail": macro_result["ingredients"],
                }
            )

    expiring_unused = await _get_expiring_unused(session, full_stock, within_days=5)

    return {
        "full_stock": full_stock,
        "shopping_required": shopping_required,
        "excluded": excluded,
        "expiring_unused_ingredients": expiring_unused,
    }


async def _get_expiring_unused(
    session: AsyncSession, full_stock_candidates: list[dict], *, within_days: int
) -> list[dict]:
    """Ingredients expiring soon that don't appear in any full-stock
    candidate -- the structural signal behind §8's "modest" expiration
    handling. Doesn't rank or phrase a suggestion; that's for the LLM
    layer once it exists."""
    cutoff = date.today() + timedelta(days=within_days)
    stmt = select(InventoryItem).where(
        InventoryItem.expiration_date.isnot(None), InventoryItem.expiration_date <= cutoff
    )
    expiring = (await session.scalars(stmt)).all()
    used_ids = {iid for c in full_stock_candidates for iid in c["ingredient_ids"]}
    return [
        {
            "inventory_id": item.id,
            "ingredient_id": item.ingredient_id,
            "expiration_date": item.expiration_date,
        }
        for item in expiring
        if item.ingredient_id not in used_ids
    ]
