"""Garmin Connect sync (kitchen_ai_spec.md §9). Uses the unofficial
python-garminconnect library (garth underneath) rather than the official
Developer Program, which is business-only with a slow approval process --
accepted tradeoff: some maintenance risk if the unofficial API breaks.

Auth is token-based after the first login: garth persists a session to
GARMIN_TOKENSTORE, and login() resumes from that without needing real
credentials again -- verified directly (a resume succeeded even with a
deliberately wrong password once tokens existed). GARMIN_EMAIL/PASSWORD
in .env are only a fallback for that resume failing; MFA can't be
completed headlessly, so if the account has MFA and tokens ever expire,
re-run scripts/garmin_login.py interactively rather than relying on this
fallback succeeding on its own.
"""

import asyncio
import os
from datetime import date, datetime
from decimal import Decimal

from garminconnect import Garmin

GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")
GARMIN_TOKENSTORE = os.environ.get("GARMIN_TOKENSTORE", "/data/garmin_tokens")


class GarminAuthRequired(Exception):
    """Tokens are missing/expired and headless resume failed -- needs
    scripts/garmin_login.py run interactively (handles MFA if needed)."""


def _prompt_mfa() -> str:
    raise GarminAuthRequired(
        "Garmin login requires an MFA code, which can't be entered headlessly. "
        "Run scripts/garmin_login.py interactively to refresh the session."
    )


def _sync_login() -> Garmin:
    client = Garmin(email=GARMIN_EMAIL, password=GARMIN_PASSWORD, prompt_mfa=_prompt_mfa)
    try:
        client.login(GARMIN_TOKENSTORE)
    except GarminAuthRequired:
        raise
    except Exception as exc:
        raise GarminAuthRequired(
            f"Garmin login failed ({type(exc).__name__}: {exc}). "
            "Run scripts/garmin_login.py interactively to (re)establish a session."
        ) from exc
    return client


def _sync_fetch_activities(start: date, end: date) -> list[dict]:
    client = _sync_login()
    return client.get_activities_by_date(start.isoformat(), end.isoformat())


async def fetch_activities(start: date, end: date) -> list[dict]:
    """Raw activity dicts from Garmin Connect for the given date range."""
    return await asyncio.to_thread(_sync_fetch_activities, start, end)


def normalize_activity(raw: dict) -> dict:
    """Maps Garmin's raw activity fields to activity_log's columns.
    Distance stays in meters (Garmin's native unit) -- not converted,
    since the spec never pinned a unit for this column either."""
    start_time_local = raw.get("startTimeLocal", "")
    activity_date = (
        datetime.strptime(start_time_local, "%Y-%m-%d %H:%M:%S").date()
        if start_time_local
        else date.today()
    )
    duration_seconds = raw.get("duration")
    return {
        "garmin_activity_id": str(raw.get("activityId")),
        "date": activity_date,
        "activity_type": raw.get("activityType", {}).get("typeKey"),
        "duration_minutes": Decimal(str(duration_seconds / 60)) if duration_seconds is not None else None,
        "distance": Decimal(str(raw["distance"])) if raw.get("distance") is not None else None,
        "calories_burned": Decimal(str(raw["calories"])) if raw.get("calories") is not None else None,
    }
