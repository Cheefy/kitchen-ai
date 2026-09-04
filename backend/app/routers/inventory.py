from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import Ingredient, InventoryItem, Unit
from app.services.units import ConversionNeedsInput, convert_to_canonical

router = APIRouter()


@router.post("/inventory", response_model=schemas.InventoryItemRead)
async def add_inventory_item(
    body: schemas.InventoryItemCreate, session: AsyncSession = Depends(get_session)
):
    ingredient = await session.get(Ingredient, body.ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="ingredient_id does not exist")

    unit = await session.get(Unit, body.unit)
    if unit is None:
        raise HTTPException(status_code=404, detail=f"unknown unit code: {body.unit!r}")

    try:
        canonical_qty, canonical_unit = convert_to_canonical(body.quantity, unit, ingredient)
    except ConversionNeedsInput as exc:
        field = "density_g_per_ml" if unit.type == "volume" else "unit_weight_g"
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "ingredient_id": ingredient.id,
                "needs_field": field,
                "resolve_via": f"PATCH /ingredients/{ingredient.id}/tier2",
            },
        ) from exc

    item = InventoryItem(
        ingredient_id=body.ingredient_id,
        quantity=canonical_qty,
        unit=canonical_unit,
        expiration_date=body.expiration_date,
        location=body.location,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/inventory", response_model=list[schemas.InventoryItemRead])
async def list_inventory(
    ingredient_id: int | None = None, session: AsyncSession = Depends(get_session)
):
    stmt = select(InventoryItem)
    if ingredient_id is not None:
        stmt = stmt.where(InventoryItem.ingredient_id == ingredient_id)
    result = await session.scalars(stmt)
    return result.all()


@router.patch("/inventory/{item_id}", response_model=schemas.InventoryItemRead)
async def update_inventory_item(
    item_id: int,
    body: schemas.InventoryItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="inventory item not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/inventory/{item_id}", status_code=204)
async def delete_inventory_item(item_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="inventory item not found")
    await session.delete(item)
    await session.commit()
