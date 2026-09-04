"""Generic <-> specific ingredient resolution (kitchen_ai_spec.md §4).
Resolution happens at read/cook time against current inventory, never at
recipe-authoring time -- recipes only ever reference a generic category.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ingredient, InventoryItem


@dataclass
class ResolvedIngredient:
    status: str  # "auto" | "needs_shopping" | "ambiguous"
    ingredient: Ingredient | None = None
    candidates: list[Ingredient] = field(default_factory=list)


async def resolve_category(session: AsyncSession, category_id: int) -> ResolvedIngredient:
    """Exactly one in-stock product -> auto-selected. Zero -> needs_shopping
    (feeds the shopping-list flow). More than one -> ambiguous, needs the
    user to pick (ask-first -- a wrong guess would use the wrong product's
    real macro data)."""
    stmt = (
        select(Ingredient)
        .join(InventoryItem, InventoryItem.ingredient_id == Ingredient.id)
        .where(Ingredient.category_id == category_id)
        .distinct()
    )
    candidates = list((await session.scalars(stmt)).all())
    if len(candidates) == 1:
        return ResolvedIngredient(status="auto", ingredient=candidates[0])
    if len(candidates) == 0:
        return ResolvedIngredient(status="needs_shopping")
    return ResolvedIngredient(status="ambiguous", candidates=candidates)
