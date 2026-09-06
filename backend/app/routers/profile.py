from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import UserProfile
from app.services.tdee import ProfileIncomplete, estimate_daily_targets, estimate_tdee

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


@router.get("/profile/targets", response_model=schemas.DailyTargetsRead)
async def get_daily_targets(session: AsyncSession = Depends(get_session)):
    """Calorie target (TDEE minus the current goal's deficit, if any) plus
    protein/fat/carbs auto-split for muscle preservation -- not manually
    entered, see app/services/tdee.py for the heuristic."""
    try:
        targets = await estimate_daily_targets(session)
    except ProfileIncomplete as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return schemas.DailyTargetsRead(
        bmr=targets.tdee.bmr,
        tdee=targets.tdee.tdee,
        activity_level=targets.tdee.activity_level,
        activity_level_is_override=targets.tdee.activity_level_is_override,
        sessions_per_week=targets.tdee.sessions_per_week,
        calibrating=targets.tdee.calibrating,
        calorie_target=targets.calorie_target,
        deficit_applied=targets.deficit_applied,
        protein_g=targets.protein_g,
        fat_g=targets.fat_g,
        carbs_g=targets.carbs_g,
    )
