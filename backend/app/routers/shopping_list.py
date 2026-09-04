from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_session
from app.models import ShoppingListItem

router = APIRouter()


@router.post("/shopping-list", response_model=schemas.ShoppingListItemRead)
async def add_shopping_list_item(
    body: schemas.ShoppingListItemCreate, session: AsyncSession = Depends(get_session)
):
    if body.ingredient_id is None and body.category_id is None:
        raise HTTPException(
            status_code=422, detail="one of ingredient_id or category_id is required"
        )
    item = ShoppingListItem(**body.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/shopping-list", response_model=list[schemas.ShoppingListItemRead])
async def list_shopping_list(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(
        select(ShoppingListItem).order_by(ShoppingListItem.date_added)
    )
    return result.all()


@router.delete("/shopping-list/{item_id}", status_code=204)
async def remove_shopping_list_item(
    item_id: int, session: AsyncSession = Depends(get_session)
):
    """kitchen_ai_spec.md §3 -- no status field; removed only on explicit
    action (here) or, in the full voice flow, when a matching barcode scan
    clears it during a post-haul inventory pass (not wired up yet)."""
    item = await session.get(ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="shopping list item not found")
    await session.delete(item)
    await session.commit()
