"""Request/response shapes for the auth endpoints."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    # Upper bound is 72, not a round number: bcrypt only looks at the first 72
    # BYTES of a password. Capping length here means every password this app
    # accepts is hashed in full, instead of silently ignoring characters past
    # byte 72 — that mismatch only becomes visible as passlib rejecting a
    # >72-byte input while probing the backend (see requirements.txt for the
    # backend probe that surfaced this). A password of pure ASCII is 1 byte per
    # character, so 72 characters here is the exact bcrypt limit; a password
    # using multi-byte Unicode could still exceed 72 bytes under this
    # character-count limit — an edge case not worth extra code for a starter.
    password: str = Field(min_length=8, max_length=72)


class UserRead(BaseModel):
    # Lets this be built straight from a SQLAlchemy User instance
    # (`UserRead.model_validate(user)`) by reading attributes instead of dict
    # keys — required because FastAPI's response_model does exactly that.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class Token(BaseModel):
    access_token: str
    # OAuth2's Bearer scheme name, expected verbatim by clients that follow the
    # spec (including FastAPI's own OAuth2PasswordBearer, which is what reads
    # this back out of the Authorization header on later requests).
    token_type: str = "bearer"
