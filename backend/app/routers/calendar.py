from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.services.calendar_view import get_calendar

router = APIRouter()


@router.get("/calendar", response_model=schemas.CalendarResponse)
async def calendar(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=6)
    return await get_calendar(session, start, end)
