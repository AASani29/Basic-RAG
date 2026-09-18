"""Engine and the per-request session dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    # Recycle before common 5-minute idle timeouts on managed Postgres and
    # cloud load balancers, which otherwise hand back a dead socket.
    pool_recycle=280,
    # Cheap liveness check on checkout; turns a stale-connection crash into a
    # transparent reconnect.
    pool_pre_ping=True,
    connect_args={
        # Supabase's pooler runs pgbouncer in transaction mode, where the
        # server connection backing your session changes between statements.
        # asyncpg caches prepared statements by name and would reference one
        # that lives on a different backend ("prepared statement _pg_x does not
        # exist"). 0 disables the cache. Costs one extra parse per query, and
        # is a harmless no-op against a direct Postgres connection.
        "statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    # Default True expires every attribute after commit, so reading
    # `item.id` on the way out triggers a lazy refresh — which raises
    # MissingGreenlet under async. Routes return ORM objects after committing,
    # so this must stay False.
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding one session per request.

    Services commit explicitly, so each one is a self-contained unit of work
    whose failure surfaces inside the route rather than after the response has
    been built. Exiting this context manager closes the session, which rolls
    back anything a failed request left uncommitted before the connection goes
    back to the pool.
    """
    async with AsyncSessionLocal() as session:
        yield session
