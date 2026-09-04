from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import Allergen, UserAllergenRestriction
from app.services.recommendations import get_recommendations

router = APIRouter()


@router.get("/recommendations", response_model=schemas.Recommendations)
async def recommendations(
    max_minutes: int | None = None, session: AsyncSession = Depends(get_session)
):
    return await get_recommendations(session, max_minutes=max_minutes)


@router.post("/allergen-restrictions", status_code=204)
async def add_allergen_restriction(
    body: schemas.AllergenRestrictionCreate, session: AsyncSession = Depends(get_session)
):
    if await session.get(Allergen, body.allergen_id) is None:
        raise HTTPException(status_code=404, detail="allergen not found")
    if await session.get(UserAllergenRestriction, body.allergen_id) is None:
        session.add(UserAllergenRestriction(allergen_id=body.allergen_id))
        await session.commit()


@router.get("/allergen-restrictions", response_model=list[schemas.AllergenRead])
async def list_allergen_restrictions(session: AsyncSession = Depends(get_session)):
    stmt = select(Allergen).join(
        UserAllergenRestriction, UserAllergenRestriction.allergen_id == Allergen.id
    )
    result = await session.scalars(stmt)
    return result.all()


@router.delete("/allergen-restrictions/{allergen_id}", status_code=204)
async def remove_allergen_restriction(
    allergen_id: int, session: AsyncSession = Depends(get_session)
):
    restriction = await session.get(UserAllergenRestriction, allergen_id)
    if restriction is None:
        raise HTTPException(status_code=404, detail="restriction not found")
    await session.delete(restriction)
    await session.commit()
