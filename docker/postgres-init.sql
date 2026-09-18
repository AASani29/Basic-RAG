-- Runs once, on first boot of an empty Postgres data volume.
-- Postgres' official entrypoint creates only the single database named by
-- POSTGRES_DB, so the test database has to be created here.
--
-- Kept separate from the app database because the test suite drops and
-- recreates its entire schema on every run.
CREATE DATABASE app_test;

-- The extension is per-database, so enabling it in `app` does nothing for
-- `app_test`. Migration 0001 also runs CREATE EXTENSION IF NOT EXISTS, which
-- makes this redundant for the app database but not for the test one, whose
-- schema is built by metadata.create_all rather than by migrations.
\connect app
CREATE EXTENSION IF NOT EXISTS vector;
\connect app_test
CREATE EXTENSION IF NOT EXISTS vector;
