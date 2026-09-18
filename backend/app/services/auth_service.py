"""Auth business logic as plain functions — no route decorators, no request
or response objects. Kept separate from api/routes/auth.py so "what makes a
registration valid" is readable and testable without FastAPI in the way.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        # 409 Conflict, not 400: the request is well-formed, it just collides
        # with existing state.
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        # Closes the race the check above leaves open: two concurrent
        # registrations for the same email can both pass that SELECT before
        # either commits, but the unique index on users.email only lets one
        # INSERT through. Without this, the loser surfaces as an unhandled 500
        # instead of the same 409 a sequential duplicate gets.
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from exc

    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> str:
    """Returns a signed access token, or raises 401."""
    user = await db.scalar(select(User).where(User.email == email))

    # Same error, same status, whether the email doesn't exist or the password
    # is wrong. Distinguishing them would let a caller enumerate which emails
    # are registered by watching which error comes back.
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if user is None or not verify_password(password, user.hashed_password):
        raise invalid

    return create_access_token(subject=str(user.id))
