"""Inventory deduction when a session's recipe ingredients get used up
(kitchen_ai_spec.md §7). Deducts from the soonest-expiring inventory rows
first (FEFO) for whichever specific ingredient the resolution service
picked for each session ingredient. All-or-nothing: raises on the first
unresolvable or insufficient ingredient rather than partially deducting.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ingredient, InventoryItem, Unit
from app.services.resolution import resolve_category
from app.services.units import convert_to_canonical, to_ingredient_basis


class InsufficientStock(Exception):
    def __init__(self, ingredient: Ingredient, needed: Decimal, available: Decimal):
        self.ingredient = ingredient
        self.needed = needed
        self.available = available
        super().__init__(
            f"'{ingredient.name}': need {needed}{ingredient.serving_size_unit}, "
            f"only {available}{ingredient.serving_size_unit} in stock"
        )


class UnresolvedIngredient(Exception):
    def __init__(self, category_id: int, status: str):
        self.category_id = category_id
        self.status = status
        super().__init__(f"category {category_id} isn't resolved to a single in-stock product ({status})")


class MixedUnitInventory(Exception):
    def __init__(self, ingredient: Ingredient, expected_unit: str, found_unit: str):
        self.ingredient = ingredient
        super().__init__(
            f"'{ingredient.name}' has inventory rows in mixed units "
            f"({expected_unit} vs {found_unit}) -- can't safely deduct yet"
        )


async def deduct_session_ingredients(session: AsyncSession, effective_ingredients: list) -> list[dict]:
    deductions = []
    for eff in effective_ingredients:
        resolved = await resolve_category(session, eff.category_id)
        if resolved.status != "auto":
            raise UnresolvedIngredient(eff.category_id, resolved.status)
        ingredient = resolved.ingredient

        unit = await session.get(Unit, eff.unit)
        canonical_qty, canonical_unit = convert_to_canonical(eff.quantity, unit, ingredient)
        needed = to_ingredient_basis(canonical_qty, canonical_unit, ingredient)
        basis_unit = ingredient.serving_size_unit

        stmt = (
            select(InventoryItem)
            .where(InventoryItem.ingredient_id == ingredient.id)
            .order_by(InventoryItem.expiration_date.asc().nulls_last())
        )
        rows = list((await session.scalars(stmt)).all())

        mismatched = next((r for r in rows if r.unit != basis_unit), None)
        if mismatched is not None:
            raise MixedUnitInventory(ingredient, basis_unit, mismatched.unit)

        available = sum((row.quantity for row in rows), Decimal("0"))
        if available < needed:
            raise InsufficientStock(ingredient, needed, available)

        remaining = needed
        for row in rows:
            if remaining <= 0:
                break
            take = min(row.quantity, remaining)
            row.quantity -= take
            remaining -= take
            if row.quantity == 0:
                await session.delete(row)

        deductions.append(
            {
                "ingredient_id": ingredient.id,
                "ingredient_name": ingredient.name,
                "deducted": needed,
                "unit": basis_unit,
            }
        )

    return deductions
