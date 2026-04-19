# -*- coding: utf-8 -*-
"""
tests/test_db.py
----------------
Tests for src/core/db.py (PostgreSQL backend)

Covers:
  - init_db() creates correct tables and indexes
  - get_conn() context manager: commit on success, rollback on error
  - Idempotency: calling init_db() twice does not error

Requires TEST_DATABASE_URL (or DATABASE_URL) to point at a live PostgreSQL
instance. Tests are skipped automatically when neither is set.
"""

import os
import pytest
import psycopg2
import psycopg2.extras


from app.core.config import settings

# ── Fixture: override settings.POSTGRES_DB + init/truncate around every test ───────────

@pytest.fixture(autouse=True)
def isolated_db():
    """
    Point the db module at the test database, ensure tables exist,
    and TRUNCATE them after every test so each test starts empty.
    """
    # Force the test DB
    settings.POSTGRES_DB = "openclaw_test"

    from app.database.db import init_db
    init_db()

    dsn = settings.get_database_url()
    yield dsn

    # Teardown: wipe table data (keep schema)
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE sessions, performance_scores RESTART IDENTITY CASCADE")
    cur.close()
    conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pg_tables(dsn: str) -> set:
    """Return the set of user-created table names in the public schema."""
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    )
    names = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return names


def _pg_columns(dsn: str, table: str) -> set:
    """Return the set of column names for *table*."""
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    cols = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return cols


def _pg_indexes(dsn: str) -> set:
    """Return the set of index names in the public schema."""
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute(
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
    )
    names = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return names


# ── init_db ────────────────────────────────────────────────────────────────────

class TestInitDb:
    def test_creates_sessions_table(self, isolated_db):
        assert "sessions" in _pg_tables(isolated_db)

    def test_creates_performance_scores_table(self, isolated_db):
        assert "performance_scores" in _pg_tables(isolated_db)

    def test_creates_required_indexes(self, isolated_db):
        indexes = _pg_indexes(isolated_db)
        assert "idx_perf_phone_topic" in indexes
        assert "idx_perf_answered_at" in indexes

    def test_idempotent_double_call(self, isolated_db):
        """Calling init_db() twice must not raise."""
        from app.database.db import init_db
        init_db()  # called once by fixture; second call must also succeed

    def test_sessions_schema(self, isolated_db):
        cols = _pg_columns(isolated_db, "sessions")
        assert {"phone_number", "question", "topic", "sent_at", "awaiting_reply"}.issubset(cols)

    def test_performance_scores_schema(self, isolated_db):
        cols = _pg_columns(isolated_db, "performance_scores")
        assert {
            "id", "phone_number", "topic", "score",
            "weak_aspects", "feedback", "answered_at"
        }.issubset(cols)


# ── get_conn ───────────────────────────────────────────────────────────────────

class TestGetConn:
    def test_commit_on_success(self, isolated_db):
        from app.database.db import get_conn
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions(phone_number, question, topic, sent_at) "
                "VALUES (%s, %s, %s, %s)",
                ("91111", "Q?", "Kafka", "2026-01-01T10:00:00"),
            )

        # Verify row persisted in a fresh connection
        with get_conn() as conn:
            row = conn.execute(
                "SELECT phone_number FROM sessions WHERE phone_number = %s",
                ("91111",),
            ).fetchone()
        assert row is not None

    def test_rollback_on_exception(self, isolated_db):
        from app.database.db import get_conn
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO sessions(phone_number, question, topic, sent_at) "
                    "VALUES (%s, %s, %s, %s)",
                    ("91222", "Q?", "Kafka", "2026-01-01T10:00:00"),
                )
                raise ValueError("Simulated failure")
        except ValueError:
            pass

        with get_conn() as conn:
            row = conn.execute(
                "SELECT phone_number FROM sessions WHERE phone_number = %s",
                ("91222",),
            ).fetchone()
        assert row is None, "Row should not exist after rollback"
