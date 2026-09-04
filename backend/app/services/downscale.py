"""Recipe auto-downscale suggestion (kitchen_ai_spec.md §3): tracks eaten-
percentage per recipe_id across fully-resolved meal_prep_batches, and
suggests a permanent scale-down when a consistent under-consumption
pattern emerges. Its own behavior_settings toggle -- some users won't
want the proactive suggestion.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MealLog, MealPrepBatch
from app.services.logging import resolve_behavior_mode

LOOKBACK = 4
MIN_SAMPLES = 3
CONSISTENCY_TOLERANCE = Decimal("0.15")
FULLY_EATEN_THRESHOLD = Decimal("0.9")


async def _eaten_fraction(session: AsyncSession, batch: MealPrepBatch) -> Decimal:
    total_eaten = await session.scalar(
        select(func.coalesce(func.sum(MealLog.quantity), 0)).where(
            MealLog.meal_prep_batch_id == batch.id
        )
    )
    return Decimal(str(total_eaten)) / batch.units_total


async def check_downscale_suggestion(session: AsyncSession, recipe_id: int) -> dict | None:
    mode = await resolve_behavior_mode(session, "recipe_downscale_suggestion", default="enabled")
    if mode == "disabled":
        return None

    stmt = (
        select(MealPrepBatch)
        .where(MealPrepBatch.recipe_id == recipe_id, MealPrepBatch.units_remaining == 0)
        .order_by(MealPrepBatch.date_prepared.desc())
        .limit(LOOKBACK)
    )
    batches = list((await session.scalars(stmt)).all())
    if len(batches) < MIN_SAMPLES:
        return None

    fractions = [await _eaten_fraction(session, b) for b in batches]

    # Any recent batch basically fully eaten -- not a consistent
    # under-consumption pattern, don't suggest.
    if any(f >= FULLY_EATEN_THRESHOLD for f in fractions):
        return None

    average = sum(fractions) / len(fractions)
    if any(abs(f - average) > CONSISTENCY_TOLERANCE for f in fractions):
        return None  # too inconsistent to call it a pattern

    return {
        "recipe_id": recipe_id,
        "sample_size": len(fractions),
        "average_eaten_fraction": average,
        "suggested_scale_factor": average,
    }
