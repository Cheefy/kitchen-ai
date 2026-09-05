from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import ActivityLog
from app.services.garmin import GarminAuthRequired, fetch_activities, normalize_activity

router = APIRouter()


@router.post("/garmin/sync", response_model=schemas.GarminSyncResult)
async def sync_garmin(days: int = 7, session: AsyncSession = Depends(get_session)):
    """kitchen_ai_spec.md §9. Deduped by garmin_activity_id so re-syncing
    an overlapping date range is safe to call repeatedly."""
    end = date.today()
    start = end - timedelta(days=days)

    try:
        raw_activities = await fetch_activities(start, end)
    except GarminAuthRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    added = 0
    skipped = 0
    for raw in raw_activities:
        normalized = normalize_activity(raw)
        existing = await session.scalar(
            select(ActivityLog).where(
                ActivityLog.garmin_activity_id == normalized["garmin_activity_id"]
            )
        )
        if existing is not None:
            skipped += 1
            continue
        session.add(ActivityLog(**normalized))
        added += 1

    await session.commit()
    return {"fetched": len(raw_activities), "added": added, "skipped_duplicates": skipped}
