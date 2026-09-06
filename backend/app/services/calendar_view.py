"""Aggregated day-by-day view combining timestamped meals + exercises with
a BMR/TDEE-based kcal deficit and expected weight change (extends spec
§8's remaining-budget concept, which never had a real BMR to work from).
The TDEE estimate is computed once from the CURRENT profile/weigh-in and
applied uniformly across every day shown -- doesn't account for weight
actually differing on past days. Good enough for a rolling week view;
would need per-day weight history to be exact.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActivityLog, Ingredient, MealLog, MealPrepBatch, Recipe
from app.services.tdee import ProfileIncomplete, estimate_tdee

CALORIES_PER_LB = Decimal("3500")


async def _meal_label(session: AsyncSession, entry: MealLog) -> str:
    if entry.recipe_id is not None:
        recipe = await session.get(Recipe, entry.recipe_id)
        return recipe.name if recipe else f"recipe #{entry.recipe_id}"
    if entry.meal_prep_batch_id is not None:
        batch = await session.get(MealPrepBatch, entry.meal_prep_batch_id)
        if batch:
            recipe = await session.get(Recipe, batch.recipe_id)
            return recipe.name if recipe else f"batch #{entry.meal_prep_batch_id}"
        return f"batch #{entry.meal_prep_batch_id}"
    if entry.ingredient_id is not None:
        ingredient = await session.get(Ingredient, entry.ingredient_id)
        return ingredient.name if ingredient else f"ingredient #{entry.ingredient_id}"
    return entry.description or "estimate"


async def get_calendar(session: AsyncSession, start: date, end: date) -> dict:
    meal_stmt = select(MealLog).where(func.date(MealLog.timestamp).between(start, end))
    meals = list((await session.scalars(meal_stmt)).all())

    exercise_stmt = select(ActivityLog).where(ActivityLog.date >= start, ActivityLog.date <= end)
    exercises = list((await session.scalars(exercise_stmt)).all())

    try:
        tdee_estimate = await estimate_tdee(session)
        tdee = tdee_estimate.tdee
        calibrating = tdee_estimate.calibrating
    except ProfileIncomplete:
        tdee = None
        calibrating = True

    meals_by_day = defaultdict(list)
    for m in meals:
        meals_by_day[m.timestamp.date()].append(m)

    exercises_by_day = defaultdict(list)
    for a in exercises:
        exercises_by_day[a.date].append(a)

    days = []
    current = start
    while current <= end:
        day_meals = meals_by_day.get(current, [])
        day_exercises = exercises_by_day.get(current, [])

        meal_entries = []
        calories_eaten = Decimal("0")
        for m in day_meals:
            cal = Decimal(str(m.macros.get("calories", 0))) if m.macros else Decimal("0")
            calories_eaten += cal
            meal_entries.append(
                {
                    "id": m.id,
                    "timestamp": m.timestamp,
                    "label": await _meal_label(session, m),
                    "calories": cal,
                    "is_estimate": m.is_estimate,
                }
            )
        meal_entries.sort(key=lambda e: e["timestamp"])

        exercise_entries = []
        calories_burned_exercise = Decimal("0")
        for a in day_exercises:
            calories_burned_exercise += a.calories_burned or Decimal("0")
            exercise_entries.append(
                {
                    "id": a.id,
                    "timestamp": a.timestamp,
                    "activity_type": a.activity_type,
                    "duration_minutes": a.duration_minutes,
                    "distance": a.distance,
                    "calories_burned": a.calories_burned,
                }
            )
        exercise_entries.sort(key=lambda e: e["timestamp"] or date.min)

        if tdee is not None:
            deficit = tdee + calories_burned_exercise - calories_eaten
            # Sign convention: positive deficit (burned more than eaten) ->
            # weight goes DOWN, so the expected change is negative.
            expected_change = -deficit / CALORIES_PER_LB
            note = None
        else:
            deficit = None
            expected_change = None
            note = "Set your profile (age/sex/height) and log a weigh-in to see deficit and expected weight change."

        days.append(
            {
                "date": current,
                "meals": meal_entries,
                "exercises": exercise_entries,
                "calories_eaten": calories_eaten,
                "calories_burned_exercise": calories_burned_exercise,
                "tdee": tdee,
                "deficit": deficit,
                "expected_weight_change_lb": expected_change,
                "calibrating": calibrating,
                "note": note,
            }
        )
        current += timedelta(days=1)

    return {"days": days}
