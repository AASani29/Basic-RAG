"""GET/POST /items, GET/PATCH/DELETE /items/{id}. All owner-scoped."""

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.item import ItemCreate, ItemPage, ItemRead, ItemUpdate
from app.services import item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=ItemPage)
async def list_items(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ItemPage:
    rows, total = await item_service.list_items(db, current_user.id, limit, offset)
    return ItemPage(items=rows, total=total, limit=limit, offset=offset)


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, db: DbSession, current_user: CurrentUser) -> ItemRead:
    return await item_service.create_item(db, current_user.id, payload)


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, db: DbSession, current_user: CurrentUser) -> ItemRead:
    return await item_service.get_item(db, item_id, current_user.id)


@router.patch("/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: int, payload: ItemUpdate, db: DbSession, current_user: CurrentUser
) -> ItemRead:
    return await item_service.update_item(db, item_id, current_user.id, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, db: DbSession, current_user: CurrentUser) -> None:
    await item_service.delete_item(db, item_id, current_user.id)
