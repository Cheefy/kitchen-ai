from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import UserProfile
from app.services.tdee import ProfileIncomplete, estimate_tdee

router = APIRouter()

VALID_SEXES = {"male", "female"}


@router.get("/profile", response_model=schemas.UserProfileRead)
async def get_profile(session: AsyncSession = Depends(get_session)):
    profile = await session.scalar(select(UserProfile).limit(1))
    if profile is None:
        raise HTTPException(status_code=404, detail="no profile set yet -- PUT /profile to create one")
    return profile


@router.put("/profile", response_model=schemas.UserProfileRead)
async def update_profile(
    body: schemas.UserProfileUpdate, session: AsyncSession = Depends(get_session)
):
    if body.biological_sex is not None and body.biological_sex not in VALID_SEXES:
        raise HTTPException(
            status_code=422, detail=f"biological_sex must be one of {sorted(VALID_SEXES)}"
        )

    profile = await session.scalar(select(UserProfile).limit(1))
    if profile is None:
        missing = [f for f in ("age", "biological_sex", "height_cm") if getattr(body, f) is None]
        if missing:
            raise HTTPException(
                status_code=422, detail=f"creating a profile requires: {missing}"
            )
        profile = UserProfile(
            age=body.age, biological_sex=body.biological_sex, height_cm=body.height_cm
        )
        session.add(profile)
    else:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)

    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/profile/tdee", response_model=schemas.TdeeRead)
async def get_tdee(session: AsyncSession = Depends(get_session)):
    try:
        return await estimate_tdee(session)
    except ProfileIncomplete as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
