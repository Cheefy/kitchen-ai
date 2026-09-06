from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import Allergen, BehaviorSetting, RecommendationSettings, UserAllergenRestriction, UserProfile

router = APIRouter()


@router.get("/settings/export", response_model=schemas.SettingsExport)
async def export_settings(session: AsyncSession = Depends(get_session)):
    """A downloadable local backup of app-level preferences -- not tied
    to a moment in time (unlike goals, weigh-ins, or logs), so it's safe
    to restore later without creating confusing dated duplicates."""
    profile = await session.scalar(select(UserProfile).limit(1))

    rec_settings = await session.scalar(select(RecommendationSettings).limit(1))
    if rec_settings is None:
        rec_settings = RecommendationSettings()
        session.add(rec_settings)
        await session.commit()
        await session.refresh(rec_settings)

    behavior_settings = (await session.scalars(select(BehaviorSetting).order_by(BehaviorSetting.key))).all()

    allergen_stmt = select(Allergen).join(
        UserAllergenRestriction, UserAllergenRestriction.allergen_id == Allergen.id
    )
    allergens = (await session.scalars(allergen_stmt)).all()

    return schemas.SettingsExport(
        exported_at=datetime.now(timezone.utc),
        profile=profile,
        recommendation_settings=rec_settings,
        behavior_settings=behavior_settings,
        allergen_restrictions=allergens,
    )


@router.post("/settings/import", response_model=schemas.SettingsImportResult)
async def import_settings(
    body: schemas.SettingsExport, session: AsyncSession = Depends(get_session)
):
    """Restores a previously exported backup. Idempotent -- safe to import
    the same file more than once without duplicating anything."""
    profile_restored = False
    if body.profile is not None:
        profile = await session.scalar(select(UserProfile).limit(1))
        if profile is None:
            profile = UserProfile(
                age=body.profile.age,
                biological_sex=body.profile.biological_sex,
                height_cm=body.profile.height_cm,
                activity_level_override=body.profile.activity_level_override,
            )
            session.add(profile)
        else:
            profile.age = body.profile.age
            profile.biological_sex = body.profile.biological_sex
            profile.height_cm = body.profile.height_cm
            profile.activity_level_override = body.profile.activity_level_override
        profile_restored = True

    rec_settings = await session.scalar(select(RecommendationSettings).limit(1))
    if rec_settings is None:
        rec_settings = RecommendationSettings()
        session.add(rec_settings)
        await session.flush()
    for field in (
        "calorie_deficit_adherence",
        "protein_adherence",
        "carb_adherence",
        "fat_adherence",
        "diversity",
        "expiration_urgency",
        "enabled_meal_slots",
        "typical_delivery_lead_hours",
        "ingredient_coverage_threshold",
    ):
        setattr(rec_settings, field, getattr(body.recommendation_settings, field))

    behavior_count = 0
    for entry in body.behavior_settings:
        setting = await session.get(BehaviorSetting, entry.key)
        if setting is None:
            session.add(BehaviorSetting(key=entry.key, mode=entry.mode))
        else:
            setting.mode = entry.mode
        behavior_count += 1

    allergen_count = 0
    for allergen in body.allergen_restrictions:
        if await session.get(Allergen, allergen.id) is None:
            continue  # allergen catalog differs on this system -- skip rather than guess
        if await session.get(UserAllergenRestriction, allergen.id) is None:
            session.add(UserAllergenRestriction(allergen_id=allergen.id))
        allergen_count += 1

    await session.commit()

    return schemas.SettingsImportResult(
        profile_restored=profile_restored,
        recommendation_settings_restored=True,
        behavior_settings_restored=behavior_count,
        allergen_restrictions_restored=allergen_count,
    )
