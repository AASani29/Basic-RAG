"""Shared pytest fixtures.

Tests run against TEST_DATABASE_URL — a REAL Postgres, not SQLite and not
mocks. pgvector's column type only exists on Postgres, so anything less
wouldn't actually test what this app does.

The schema is built with Base.metadata.create_all(), not by running Alembic
migrations. That's faster (no migration history to replay) and means the
migrations themselves go untested by this suite — an accepted trade-off at
this size; see README.

No fixture stubs Groq or the embedding model. It doesn't need to: the one RAG
test (chat with no documents) hits answer_question's first short-circuit,
which returns before either is ever called — see rag_service.py. That's what
keeps this whole suite runnable with no API keys configured.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import get_session
from app.main import create_app

settings = get_settings()


@pytest_asyncio.fixture
async def _test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """A FRESH engine for every single test, not a shared module-level one.

    asyncpg connections are bound to the asyncio event loop they were opened
    on, and pytest-asyncio gives each test function its own event loop by
    default. A module-level engine created once would have its pooled
    connections tied to whichever test happened to touch it first — every
    later test would then hit "another operation is in progress" or similar,
    since it's running on a different loop. Building (and disposing) the
    engine inside this function-scoped fixture means it only ever exists
    within a single test's own loop, so this can't happen regardless of how
    pytest-asyncio's own loop scoping is configured.

    drop_all before create_all, every time: guarantees each test starts from
    a genuinely empty schema, so tests can't leak state into each other
    regardless of execution order.
    """
    engine = create_async_engine(
        settings.test_database_url,
        # Same pgbouncer-safety reasoning as db/session.py — harmless against
        # a direct connection, required against a transaction-mode pooler.
        connect_args={"statement_cache_size": 0},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(_test_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """An HTTP client wired to the app in-process — no real server, no open
    port. dependency_overrides swaps the app's real DB session for one bound
    to this test's own engine; everything else (middleware, exception
    handlers, routes) runs exactly as it does in production.
    """
    test_session_local = async_sessionmaker(_test_engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_local() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Registers and logs in a throwaway user, returns ready-to-use auth
    headers. Every test that needs an authenticated user takes this fixture
    instead of repeating the register-then-login boilerplate.
    """
    await client.post(
        "/auth/register", json={"email": "fixture@example.com", "password": "password123"}
    )
    r = await client.post(
        "/auth/login", data={"username": "fixture@example.com", "password": "password123"}
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
