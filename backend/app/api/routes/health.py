"""Liveness + dependency check."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: DbSession) -> dict[str, str]:
    """Reports healthy only if the database actually answers.

    A health check that returns 200 while the database is unreachable is worse
    than none: an orchestrator keeps routing traffic to a process that cannot
    serve a single real request. The SELECT 1 round-trip is what makes this
    honest.
    """
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
