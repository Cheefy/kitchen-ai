from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import BehaviorSetting

router = APIRouter()


@router.get("/behavior-settings", response_model=list[schemas.BehaviorSettingRead])
async def list_behavior_settings(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(BehaviorSetting).order_by(BehaviorSetting.key))
    return result.all()


@router.put("/behavior-settings/{key}", response_model=schemas.BehaviorSettingRead)
async def upsert_behavior_setting(
    key: str, body: schemas.BehaviorSettingUpsert, session: AsyncSession = Depends(get_session)
):
    setting = await session.get(BehaviorSetting, key)
    if setting is None:
        setting = BehaviorSetting(key=key, mode=body.mode)
        session.add(setting)
    else:
        setting.mode = body.mode
    await session.commit()
    await session.refresh(setting)
    return setting
