"""Assumption logging (kitchen_ai_spec.md §3, system_log). Phase 1 infra --
built before feature work so real assumption data exists from the start.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BehaviorSetting, SystemLog

DEBUG_LOGGING = os.environ.get("DEBUG_LOGGING", "false").lower() == "true"


async def resolve_behavior_mode(
    session: AsyncSession, behavior_key: str, default: str = "assume_and_announce"
) -> str:
    setting = await session.get(BehaviorSetting, behavior_key)
    return setting.mode if setting else default


async def log_assumption(
    session: AsyncSession,
    *,
    behavior_key: str,
    description: str,
    trigger: str | None = None,
    corrected: bool = False,
    debug_detail: dict | None = None,
) -> SystemLog:
    entry = SystemLog(
        description=description,
        trigger=trigger,
        behavior_key=behavior_key,
        corrected=corrected,
        debug_detail=debug_detail if DEBUG_LOGGING else None,
    )
    session.add(entry)
    await session.flush()
    return entry
