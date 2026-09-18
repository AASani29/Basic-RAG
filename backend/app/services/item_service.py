"""Items CRUD — plain functions, every one of them owner-scoped.

There is no "list everyone's items" or admin path anywhere in this file. This
template has no roles, so the only correct scope for any item operation is
"the current user's own" — that omission is deliberate, not unfinished.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Item
from app.schemas.item import ItemCreate, ItemUpdate


async def list_items(
    db: AsyncSession, owner_id: int, limit: int, offset: int
) -> tuple[list[Item], int]:
    total = await db.scalar(select(func.count()).select_from(Item).where(Item.owner_id == owner_id))
    rows = await db.scalars(
        select(Item)
        .where(Item.owner_id == owner_id)
        # id as a tiebreaker: two items created in the same instant would
        # otherwise have equal created_at, and without a total order pagination
        # can show a row twice or skip one across page boundaries.
        .order_by(Item.created_at.desc(), Item.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def create_item(db: AsyncSession, owner_id: int, payload: ItemCreate) -> Item:
    item = Item(title=payload.title, description=payload.description, owner_id=owner_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def get_item(db: AsyncSession, item_id: int, owner_id: int) -> Item:
    item = await db.scalar(select(Item).where(Item.id == item_id, Item.owner_id == owner_id))
    if item is None:
        # 404, not 403. Folding owner_id into the SAME query that looks the
        # row up — rather than fetching by id first and checking ownership
        # after — is what makes "exists but isn't yours" indistinguishable
        # from "no such id". A 403 here would confirm the id exists at all.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


async def update_item(db: AsyncSession, item_id: int, owner_id: int, payload: ItemUpdate) -> Item:
    item = await get_item(db, item_id, owner_id)
    # exclude_unset, not exclude_none: see the comment on ItemUpdate. Only
    # fields the client actually included in the request body get applied.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, item_id: int, owner_id: int) -> None:
    item = await get_item(db, item_id, owner_id)
    await db.delete(item)
    await db.commit()
