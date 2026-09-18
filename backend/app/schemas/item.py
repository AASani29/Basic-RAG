"""Request/response shapes for the items resource."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ItemUpdate(BaseModel):
    # Both fields optional and default to None: PATCH means "change only what
    # you send" (PUT would mean "replace the whole resource"). Whether a field
    # was actually sent is read from model_fields_set in the service, via
    # model_dump(exclude_unset=True) — NOT from whether the value is None,
    # because {"description": null} (clear it) and omitting description
    # entirely (leave it alone) both need to work and are different requests.
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    owner_id: int
    created_at: datetime


class ItemPage(BaseModel):
    items: list[ItemRead]
    # Total row count for the whole query, not len(items) — what the frontend
    # needs to render "page 3 of 12" or disable a Next button.
    total: int
    limit: int
    offset: int
