from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import SystemLog

router = APIRouter()


@router.get("/system-log", response_model=list[schemas.SystemLogRead])
async def list_system_log(
    behavior_key: str | None = None,
    corrected: bool | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    """kitchen_ai_spec.md §3 -- meant to be reviewed systematically (e.g.
    bulk-exported for pattern review), so this stays filterable rather than
    a flat dump."""
    stmt = select(SystemLog).order_by(SystemLog.timestamp.desc()).limit(limit)
    if behavior_key is not None:
        stmt = stmt.where(SystemLog.behavior_key == behavior_key)
    if corrected is not None:
        stmt = stmt.where(SystemLog.corrected == corrected)
    result = await session.scalars(stmt)
    return result.all()


@router.patch("/system-log/{entry_id}/mark-corrected", response_model=schemas.SystemLogRead)
async def mark_corrected(entry_id: int, session: AsyncSession = Depends(get_session)):
    """Flags that the user later overrode this assumption -- a pattern of
    these against one behavior_key is the signal to reconsider its
    default (kitchen_ai_spec.md §3)."""
    entry = await session.get(SystemLog, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="system_log entry not found")
    entry.corrected = True
    await session.commit()
    await session.refresh(entry)
    return entry
