"""Deficit/date solver (kitchen_ai_spec.md §3, user_goals). Whichever of
target_deficit_surplus / target_date was provided is the fixed input; the
other gets solved for. goal_weight is the anchor and never auto-recalculates.
"""

from datetime import date, timedelta
from decimal import Decimal

# The spec also mentions 7700/kg for metric users -- not yet a configurable
# unit toggle, so this assumes pounds.
CALORIES_PER_LB = Decimal("3500")


def solve_goal(
    *,
    current_weight: Decimal,
    goal_weight: Decimal,
    target_deficit_surplus: Decimal | None,
    target_date: date | None,
    today: date,
) -> tuple[Decimal | None, date | None]:
    total_calories_needed = (current_weight - goal_weight) * CALORIES_PER_LB

    if target_deficit_surplus is not None and target_date is None:
        if target_deficit_surplus == 0:
            return target_deficit_surplus, None
        days_needed = total_calories_needed / target_deficit_surplus
        solved_date = today + timedelta(days=float(days_needed)) if days_needed > 0 else today
        return target_deficit_surplus, solved_date

    if target_date is not None and target_deficit_surplus is None:
        days_until = (target_date - today).days
        if days_until <= 0:
            return None, target_date
        solved_deficit = total_calories_needed / Decimal(days_until)
        return solved_deficit, target_date

    # Both given, or neither -- keep as provided.
    return target_deficit_surplus, target_date
