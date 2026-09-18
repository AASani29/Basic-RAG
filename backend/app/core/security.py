"""Password hashing and JWT creation/verification.

Pure functions only — no DB import, no FastAPI import. That means these can be
unit tested with zero fixtures, and it keeps "how do I prove a password is
right" separate from "how do I load a user", which is a different concern
(auth_service.py) and a different one again (deps.py, which turns a token into
a request-scoped user).
"""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# Single scheme (bcrypt). `deprecated="auto"` is passlib's flag for migrating
# off an old scheme when you add a new one to this list — we only ever have
# one, but it costs nothing to leave on and means adding a stronger scheme
# later needs no code change here, just a new entry in `schemes`.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """`subject` is the user id, already stringified.

    JWT's `sub` claim is conventionally a string identifier — python-jose does
    not coerce an int for you, and decoding later gives back whatever type was
    encoded, so the string conversion has to happen on the way in.
    """
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Returns the subject (user id as a string).

    Raises jose.JWTError for ANY failure — bad signature, malformed token, or
    expired token (jose checks `exp` by default and raises a JWTError subclass
    for it). The caller doesn't need to tell these apart: every case is a 401.
    """
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    subject = payload.get("sub")
    if subject is None:
        raise JWTError("token missing sub claim")
    return subject
