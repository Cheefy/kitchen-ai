"""BMR/TDEE estimate (kitchen_ai_spec.md §2). Mifflin-St Jeor formula using
the user's profile (age/sex/height) and their most recent weigh-in for
current weight. This is the uncalibrated baseline -- NOT the personal-
calibration correction factor, which needs weeks of paired predicted-vs-
actual data and isn't built yet (flagged via `calibrating=True` below,
per the spec's own "still calibrating" language).

activity_level is deliberately never stored: it's derived fresh from a
rolling window of activity_log on every call, so a real change in
exercise habits is reflected automatically rather than needing anyone to
notice and update a stored value.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActivityLog, UserProfile, WeighIn

LB_TO_KG = Decimal("0.45359237")

ACTIVITY_MULTIPLIERS = {
    "sedentary": Decimal("1.2"),
    "lightly_active": Decimal("1.375"),
    "moderately_active": Decimal("1.55"),
    "very_active": Decimal("1.725"),
    "extra_active": Decimal("1.9"),
}

ACTIVITY_LOOKBACK_DAYS = 30


@dataclass
class TdeeEstimate:
    bmr: Decimal
    activity_level: str
    activity_level_is_override: bool
    sessions_per_week: Decimal | None
    tdee: Decimal
    calibrating: bool  # always True until the weeks-long calibration loop (§2) exists


class ProfileIncomplete(Exception):
    pass


async def infer_activity_level(session: AsyncSession, *, today: date | None = None) -> tuple[str, Decimal]:
    """Classifies activity level by real exercise frequency over a rolling
    window, not a fixed label -- so it tracks actual current behavior."""
    today = today or date.today()
    window_start = today - timedelta(days=ACTIVITY_LOOKBACK_DAYS)
    count = await session.scalar(
        select(func.count()).select_from(ActivityLog).where(ActivityLog.date >= window_start, ActivityLog.date <= today)
    )
    sessions_per_week = (Decimal(count or 0) / Decimal(ACTIVITY_LOOKBACK_DAYS)) * 7

    if sessions_per_week < 1:
        level = "sedentary"
    elif sessions_per_week < 3:
        level = "lightly_active"
    elif sessions_per_week < 5:
        level = "moderately_active"
    elif sessions_per_week < 7:
        level = "very_active"
    else:
        level = "extra_active"

    return level, sessions_per_week


def calculate_bmr(*, weight_kg: Decimal, height_cm: Decimal, age: int, biological_sex: str) -> Decimal:
    base = Decimal("10") * weight_kg + Decimal("6.25") * height_cm - Decimal("5") * age
    return base + 5 if biological_sex == "male" else base - 161


async def estimate_tdee(session: AsyncSession) -> TdeeEstimate:
    profile = await session.scalar(select(UserProfile).limit(1))
    if profile is None:
        raise ProfileIncomplete("no profile set -- PUT /profile with age/biological_sex/height_cm first")

    latest_weigh_in = await session.scalar(select(WeighIn).order_by(WeighIn.date.desc()).limit(1))
    if latest_weigh_in is None:
        raise ProfileIncomplete("no weigh-ins logged yet -- BMR needs a current weight")

    weight_kg = latest_weigh_in.weight * LB_TO_KG
    bmr = calculate_bmr(
        weight_kg=weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        biological_sex=profile.biological_sex,
    )

    if profile.activity_level_override:
        activity_level = profile.activity_level_override
        sessions_per_week = None
        is_override = True
    else:
        activity_level, sessions_per_week = await infer_activity_level(session)
        is_override = False

    tdee = bmr * ACTIVITY_MULTIPLIERS[activity_level]

    return TdeeEstimate(
        bmr=bmr,
        activity_level=activity_level,
        activity_level_is_override=is_override,
        sessions_per_week=sessions_per_week,
        tdee=tdee,
        calibrating=True,
    )
