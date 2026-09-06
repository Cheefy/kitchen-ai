from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import ActivityLog, PlannedMeal, RecommendationSettings, UserGoal, WeighIn
from app.services.goals import solve_goal

router = APIRouter()


# --- Activity log (Garmin sync writes here, §9) -----------------------------


@router.get("/activity-log", response_model=list[schemas.ActivityLogRead])
async def list_activity_log(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(ActivityLog).order_by(ActivityLog.date.desc()))
    return result.all()


# --- Weigh-ins ---------------------------------------------------------


@router.post("/weigh-ins", response_model=schemas.WeighInRead)
async def create_weigh_in(
    body: schemas.WeighInCreate, session: AsyncSession = Depends(get_session)
):
    entry = WeighIn(**body.model_dump())
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.get("/weigh-ins", response_model=list[schemas.WeighInRead])
async def list_weigh_ins(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(WeighIn).order_by(WeighIn.date.desc()))
    return result.all()


@router.delete("/weigh-ins/{weigh_in_id}", status_code=204)
async def delete_weigh_in(weigh_in_id: int, session: AsyncSession = Depends(get_session)):
    entry = await session.get(WeighIn, weigh_in_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="weigh-in not found")
    await session.delete(entry)
    await session.commit()


# --- Goals -----------------------------------------------------------------


@router.post("/goals", response_model=schemas.UserGoalRead)
async def create_goal(
    body: schemas.UserGoalCreate, session: AsyncSession = Depends(get_session)
):
    latest_weigh_in = await session.scalar(
        select(WeighIn).order_by(WeighIn.date.desc()).limit(1)
    )
    if latest_weigh_in is None:
        raise HTTPException(
            status_code=409, detail="need at least one weigh-in to solve deficit/date"
        )

    deficit, target_date = solve_goal(
        current_weight=latest_weigh_in.weight,
        goal_weight=body.goal_weight,
        target_deficit_surplus=body.target_deficit_surplus,
        target_date=body.target_date,
        today=body.effective_date,
    )

    goal = UserGoal(
        effective_date=body.effective_date,
        goal_type=body.goal_type,
        protein_g=body.protein_g,
        fat_g=body.fat_g,
        carbs_g=body.carbs_g,
        goal_weight=body.goal_weight,
        target_deficit_surplus=deficit,
        target_date=target_date,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return goal


@router.get("/goals", response_model=list[schemas.UserGoalRead])
async def list_goals(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(UserGoal).order_by(UserGoal.effective_date.desc()))
    return result.all()


@router.get("/goals/current", response_model=schemas.UserGoalRead)
async def get_current_goal(session: AsyncSession = Depends(get_session)):
    goal = await session.scalar(
        select(UserGoal).order_by(UserGoal.effective_date.desc()).limit(1)
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="no goals set yet")
    return goal


# --- Recommendation settings -------------------------------------------------


@router.get(
    "/recommendation-settings", response_model=schemas.RecommendationSettingsRead
)
async def get_recommendation_settings(session: AsyncSession = Depends(get_session)):
    settings = await session.scalar(select(RecommendationSettings).limit(1))
    if settings is None:
        # kitchen_ai_spec.md §3 -- single current-state row, seeded with the
        # model's own defaults (calorie/protein high, carb/fat low, etc).
        settings = RecommendationSettings()
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


@router.patch(
    "/recommendation-settings", response_model=schemas.RecommendationSettingsRead
)
async def update_recommendation_settings(
    body: schemas.RecommendationSettingsUpdate,
    session: AsyncSession = Depends(get_session),
):
    settings = await session.scalar(select(RecommendationSettings).limit(1))
    if settings is None:
        settings = RecommendationSettings()
        session.add(settings)
        await session.flush()
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    await session.commit()
    await session.refresh(settings)
    return settings


# --- Planned meals -----------------------------------------------------------


@router.post("/planned-meals", response_model=schemas.PlannedMealRead)
async def create_planned_meal(
    body: schemas.PlannedMealCreate, session: AsyncSession = Depends(get_session)
):
    entry = PlannedMeal(**body.model_dump())
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.get("/planned-meals", response_model=list[schemas.PlannedMealRead])
async def list_planned_meals(session: AsyncSession = Depends(get_session)):
    """kitchen_ai_spec.md §3 -- same-day only. Filtered to today here since
    there's no scheduled job in this stack yet to actually clear stale rows
    at the day boundary; they'd just stop showing up in this list."""
    stmt = select(PlannedMeal).where(PlannedMeal.date == date_type.today())
    result = await session.scalars(stmt)
    return result.all()


@router.delete("/planned-meals/{entry_id}", status_code=204)
async def delete_planned_meal(entry_id: int, session: AsyncSession = Depends(get_session)):
    entry = await session.get(PlannedMeal, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="planned meal not found")
    await session.delete(entry)
    await session.commit()
