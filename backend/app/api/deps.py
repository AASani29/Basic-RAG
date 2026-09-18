"""Dependencies shared across routes: the DB session and the current user.

Declared once here as `Annotated` aliases so every route signature is a
one-liner (`db: DbSession`, `user: CurrentUser`) instead of repeating
`Depends(...)` at every call site.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]

# tokenUrl only feeds Swagger UI's "Authorize" button (where it POSTs a
# login form from inside /docs) — it has no effect on how a real request's
# token is checked below.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    # One exception instance reused for every failure branch below, so a
    # missing user and a tampered token are indistinguishable to the caller —
    # telling them apart would let someone probe which user ids exist.
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        # Per the Bearer auth spec (RFC 6750) — some HTTP clients use this
        # header to decide whether to prompt for re-auth.
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        subject = decode_access_token(token)
        user_pk = int(subject)
    except (JWTError, ValueError) as exc:
        # ValueError covers a syntactically valid, correctly-signed token whose
        # `sub` isn't an integer string — can't happen with tokens this app
        # issues, but a hand-crafted token could still reach here.
        raise credentials_error from exc

    # .get() is a primary-key lookup — the cheapest possible query, and reads
    # through SQLAlchemy's identity map if this session already touched the row.
    user = await db.get(User, user_pk)
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
