"""Unit conversion (kitchen_ai_spec.md §5). Canonical storage is grams for
mass, ml for volume. Tier 1 (mass<->mass, volume<->volume) always succeeds
via the `units` table. Tier 2 (a `count` unit, or bridging g<->ml) needs
ingredient-specific data -- raises ConversionNeedsInput when that isn't set
yet, so the caller can ask once and backfill it rather than guessing.
"""

from decimal import Decimal

from app.models import Ingredient, Unit


class ConversionNeedsInput(Exception):
    def __init__(self, ingredient: Ingredient, field: str, reason: str):
        self.ingredient = ingredient
        self.field = field
        super().__init__(f"'{ingredient.name}' has no {field} set -- {reason}")


def convert_to_canonical(
    quantity: Decimal, unit: Unit, ingredient: Ingredient
) -> tuple[Decimal, str]:
    """Resolves quantity+unit to canonical units (g for mass, ml for
    volume). `count` needs ingredient.unit_weight_g."""
    if unit.type == "mass":
        return quantity * unit.to_canonical_factor, "g"
    if unit.type == "volume":
        return quantity * unit.to_canonical_factor, "ml"
    if ingredient.unit_weight_g is None:
        raise ConversionNeedsInput(
            ingredient,
            "unit_weight_g",
            f"can't convert a count quantity ('{unit.code}') to canonical units yet.",
        )
    return quantity * ingredient.unit_weight_g, "g"


def to_ingredient_basis(
    canonical_qty: Decimal, canonical_unit: str, ingredient: Ingredient
) -> Decimal:
    """Bridges g<->ml via density when a canonical quantity is in a
    different basis than the one the ingredient's macros are reported in
    (e.g. a recipe gives volume for something whose label reports macros
    per gram)."""
    if canonical_unit == ingredient.serving_size_unit:
        return canonical_qty
    if ingredient.density_g_per_ml is None:
        raise ConversionNeedsInput(
            ingredient,
            "density_g_per_ml",
            f"can't convert {canonical_unit} to {ingredient.serving_size_unit} for macro calculation.",
        )
    if canonical_unit == "ml":
        return canonical_qty * ingredient.density_g_per_ml
    return canonical_qty / ingredient.density_g_per_ml
