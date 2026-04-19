-- db_init/postgres-init.sql
-- Runs automatically when the postgres container first starts.
-- Creates the application DB (already exists as POSTGRES_DB) and the test DB.

SELECT 'CREATE DATABASE openclaw_test OWNER postgres'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'openclaw_test'
)\gexec
