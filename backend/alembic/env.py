"""Alembic environment.

Generated from Alembic's async template, then changed in three ways:
  1. the URL comes from app settings, not alembic.ini, so there is one place
     secrets live and no credentials sit in a tracked file;
  2. target_metadata points at our Base so `alembic revision --autogenerate`
     can diff the models against the database;
  3. models are imported for their side effect of registering on that metadata.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.db.models import Base  # noqa: F401 -- imported so the tables register

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injected at runtime rather than stored in alembic.ini, which is committed.
# escape("%") because ConfigParser treats a bare % as interpolation syntax and
# would choke on a password containing one.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (`alembic upgrade head --sql`).

    Useful when a DBA has to review or apply the change by hand.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Without this, autogenerate ignores a changed column type (e.g.
        # String(200) -> String(400)) and silently produces an empty migration.
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # Migrations are a one-shot process; a connection pool would just delay
        # exit while it waits for idle connections to close.
        poolclass=pool.NullPool,
        # Same pgbouncer constraint as the app engine — see db/session.py.
        connect_args={"statement_cache_size": 0},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
