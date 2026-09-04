"""Unit conversion (kitchen_ai_spec.md §5). Canonical storage is grams for
mass, ml for volume. Tier 1 (mass<->mass, volume<->volume) always succeeds
via the `units` table. Tier 2 (a `count` unit) needs the ingredient's
unit_weight_g -- raises ConversionNeedsInput if that isn't set yet, so the
caller can ask once and backfill it rather than guessing.
"""

from decimal import Decimal

from app.models import Ingredient, Unit


class ConversionNeedsInput(Exception):
    def __init__(self, ingredient: Ingredient, unit: Unit):
        self.ingredient = ingredient
        self.unit = unit
        field = "density_g_per_ml" if unit.type == "volume" else "unit_weight_g"
        super().__init__(
            f"'{ingredient.name}' has no {field} set -- can't convert a "
            f"{unit.type} quantity ('{unit.code}') to canonical units yet."
        )


def convert_to_canonical(
    quantity: Decimal, unit: Unit, ingredient: Ingredient
) -> tuple[Decimal, str]:
    if unit.type == "mass":
        return quantity * unit.to_canonical_factor, "g"
    if unit.type == "volume":
        return quantity * unit.to_canonical_factor, "ml"
    # count
    if ingredient.unit_weight_g is None:
        raise ConversionNeedsInput(ingredient, unit)
    return quantity * ingredient.unit_weight_g, "g"
