"""Live recipe macro computation (kitchen_ai_spec.md §3): "Macros are never
stored directly -- always computed live from the ingredient join, so
substitutions and edits recalculate automatically with no caching to keep
in sync." This is that computation.
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RecipeIngredient, Unit
from app.services.resolution import resolve_category
from app.services.units import ConversionNeedsInput, convert_to_canonical, to_ingredient_basis

MACRO_FIELDS = ["calories", "protein_g", "carbs_g", "fat_g"]


def floatify_macros(macros: dict) -> dict:
    """JSONB columns serialize via plain json.dumps, which chokes on
    Decimal -- convert before writing anywhere macros get stored."""
    return {k: float(v) for k, v in macros.items() if v is not None}


async def compute_recipe_macros(
    session: AsyncSession, recipe_ingredients: list[RecipeIngredient]
) -> dict:
    totals = {f: Decimal("0") for f in MACRO_FIELDS}
    lines = []
    fully_resolved = True

    for ri in recipe_ingredients:
        resolved = await resolve_category(session, ri.category_id)
        line = {
            "recipe_ingredient_id": ri.id,
            "category_id": ri.category_id,
            "resolution": resolved.status,
        }

        if resolved.status != "auto":
            fully_resolved = False
            if resolved.candidates:
                line["candidate_ingredient_ids"] = [c.id for c in resolved.candidates]
            lines.append(line)
            continue

        ingredient = resolved.ingredient
        line["ingredient_id"] = ingredient.id
        line["ingredient_name"] = ingredient.name

        unit = await session.get(Unit, ri.unit)
        try:
            canonical_qty, canonical_unit = convert_to_canonical(ri.quantity, unit, ingredient)
            basis_qty = to_ingredient_basis(canonical_qty, canonical_unit, ingredient)
        except ConversionNeedsInput as exc:
            fully_resolved = False
            line["resolution"] = "needs_conversion_input"
            line["error"] = str(exc)
            lines.append(line)
            continue

        if not ingredient.serving_size:
            fully_resolved = False
            line["resolution"] = "missing_macro_data"
            lines.append(line)
            continue

        scale = basis_qty / ingredient.serving_size
        for f in MACRO_FIELDS:
            value = getattr(ingredient, f)
            if value is not None:
                totals[f] += value * scale
        line["scale"] = scale
        lines.append(line)

    return {"fully_resolved": fully_resolved, "totals": totals, "ingredients": lines}
