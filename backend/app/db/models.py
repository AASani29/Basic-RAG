"""SQLAlchemy models — three tables, no inheritance, no mixins.

Note there are no `relationship()` attributes. Nothing in this app navigates
from a user to its items in Python; every service issues an explicit query
filtered by owner_id. Under async SQLAlchemy an unloaded relationship raises
MissingGreenlet the moment something touches it, so declaring relationships we
never load would add a footgun and no capability.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 320 = the maximum length of an email address per RFC 5321.
    # Unique because it is the login identifier; enforced by the database so a
    # race between two concurrent registrations cannot create a duplicate.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # The bcrypt hash, never the password. Always 60 chars for bcrypt, but sized
    # larger so swapping the algorithm later does not need a migration.
    hashed_password: Mapped[str] = mapped_column(String(128))
    # server_default so the database stamps the time. A Python-side default
    # would use the app server's clock, which drifts from the DB's.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ondelete CASCADE: deleting a user must not leave orphan rows pointing at
    # a vanished id. Enforced in the database, so it holds for the seed script
    # and manual psql sessions too, not just for traffic through the ORM.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentChunk(Base):
    """One embedded slice of an uploaded document.

    There is no parent `documents` table. `filename` is denormalised onto the
    chunk because the only document-level fact anything needs is the name shown
    on a citation. A parent table earns its place when you add delete-by-
    document or re-indexing; until then it would be a join for nothing.
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Retrieval filters on this. Without it, one user's question could match
    # another user's document — the quiet multi-tenancy bug in most RAG demos.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    # Position within the source document, so a citation can say "chunk 3 of
    # report.pdf" and chunks can be re-assembled in order.
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Width is fixed at table-creation time, which is why EMBEDDING_DIM cannot
    # be changed by env alone — it needs a migration. Must match EMBEDDING_MODEL.
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Composite index on the two columns retrieval always uses together.
        Index("ix_document_chunks_owner_filename", "owner_id", "filename"),
    )
