from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
