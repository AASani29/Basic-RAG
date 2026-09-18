"""POST /auth/register, POST /auth/login, GET /auth/me."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.schemas.user import Token, UserCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: UserCreate, db: DbSession) -> UserRead:
    # 201 Created: this endpoint's whole job is creating a new resource, which
    # is what that status code specifically means, as opposed to the default 200.
    return await auth_service.register_user(db, payload.email, payload.password)


@router.post("/login", response_model=Token)
async def login(
    db: DbSession,
    # OAuth2PasswordRequestForm parses `application/x-www-form-urlencoded`
    # fields named `username`/`password` — that field naming comes from the
    # OAuth2 password grant spec, not a choice made here. The frontend sends
    # the user's email in the `username` field.
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    token = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    # All the auth work already happened inside the CurrentUser dependency —
    # reaching this line at all proves the token was valid.
    return current_user
