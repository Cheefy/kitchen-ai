from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import Cookware

router = APIRouter()


@router.post("/cookware", response_model=schemas.CookwareRead)
async def create_cookware(
    body: schemas.CookwareCreate, session: AsyncSession = Depends(get_session)
):
    item = Cookware(**body.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/cookware", response_model=list[schemas.CookwareRead])
async def list_cookware(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(Cookware).order_by(Cookware.name))
    return result.all()


@router.get("/cookware/{cookware_id}", response_model=schemas.CookwareRead)
async def get_cookware(cookware_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(Cookware, cookware_id)
    if item is None:
        raise HTTPException(status_code=404, detail="cookware not found")
    return item


@router.patch("/cookware/{cookware_id}", response_model=schemas.CookwareRead)
async def update_cookware(
    cookware_id: int, body: schemas.CookwareUpdate, session: AsyncSession = Depends(get_session)
):
    item = await session.get(Cookware, cookware_id)
    if item is None:
        raise HTTPException(status_code=404, detail="cookware not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/cookware/{cookware_id}", status_code=204)
async def delete_cookware(cookware_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(Cookware, cookware_id)
    if item is None:
        raise HTTPException(status_code=404, detail="cookware not found")

    await session.delete(item)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="this cookware is required by a recipe -- remove it there first"
        ) from exc
