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

Postmortem (Sept 2026): the deployed backend once returned {"fetched": 0}
indefinitely while a one-off `docker compose exec ... python -c ...`
using this exact same code path returned real activities every time.
Root cause: garminconnect's login() does a proactive DI-token refresh
that is wrapped in a broad try/except logging only at DEBUG (invisible
under normal INFO logging), and get_activities_by_date()'s pagination
loop treats *any* falsy page from connectapi() -- including one caused
by that swallowed refresh failure -- identically to "no more pages",
returning an empty list with no exception and no visible log line. A
brand-new process (a fresh `docker exec`, or a container restart) gets
a clean token load with nothing to refresh, so it just works -- which
is exactly what made this look like it "worked everywhere except here".
`docker compose restart backend` alone fixed it with no code change.
_sync_fetch_activities() below now retries once with a completely fresh
login before trusting an empty result, and logs loudly either way so a
recurrence shows up in `docker compose logs backend` instead of hiding
as a silent {"fetched": 0}.
"""

import asyncio
import logging
import os
from datetime import date, datetime
from decimal import Decimal

from garminconnect import Garmin

logger = logging.getLogger(__name__)

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
    activities = client.get_activities_by_date(start.isoformat(), end.isoformat())

    if not activities:
        # See the postmortem in this module's docstring: an empty result can
        # mean a genuinely empty date range, or it can mean the long-running
        # process's login() silently failed to refresh a near-expiry token.
        # Both look identical from here (no exception, no log line from the
        # library), so don't trust a first empty result -- retry once with a
        # brand-new client/login, which is the one thing we've confirmed
        # reliably clears the stale-session case.
        logger.warning(
            "Garmin returned 0 activities for %s..%s on the first attempt; "
            "retrying once with a fresh login before accepting it as empty.",
            start,
            end,
        )
        client = _sync_login()
        activities = client.get_activities_by_date(start.isoformat(), end.isoformat())
        if activities:
            logger.warning(
                "Retry with a fresh login recovered %d activities for %s..%s -- "
                "the first attempt's empty result was a stale session, not a "
                "real empty range.",
                len(activities),
                start,
                end,
            )
        else:
            logger.warning(
                "Garmin still returned 0 activities for %s..%s after a fresh "
                "login retry; accepting this as a genuinely empty range.",
                start,
                end,
            )

    return activities


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
