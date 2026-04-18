"""
src/core/db.py
--------------
Central PostgreSQL connection manager (replaces the old SQLite coach.db).

Connection DSN is read from the DATABASE_URL environment variable:
    postgresql://user:password@host:port/dbname

Public API (unchanged from the SQLite version):
    init_db()   — create tables & indexes at startup
    get_conn()  — context manager yielding a connection wrapper

The yielded wrapper exposes the same `.execute() / .executemany()` interface
as sqlite3.Connection so all callers (session.py, performance.py) need only
minimal changes (placeholder style: %s instead of ?).
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from src.core.logger import get_logger
from src.core.sys_config import settings

logger = get_logger("CoachDB")


# ── Schema DDL ──────────────────────────────────────────────────────────────────

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id              SERIAL PRIMARY KEY,
    phone_number    TEXT NOT NULL,
    question        TEXT NOT NULL,
    topic           TEXT NOT NULL,
    sent_at         TEXT NOT NULL,
    awaiting_reply  INTEGER DEFAULT 1
);
"""

_CREATE_PERFORMANCE = """
CREATE TABLE IF NOT EXISTS performance_scores (
    id              SERIAL PRIMARY KEY,
    phone_number    TEXT NOT NULL,
    topic           TEXT NOT NULL,
    score           INTEGER NOT NULL,
    weak_aspects    TEXT,
    feedback        TEXT,
    answered_at     TEXT NOT NULL
);
"""

_CREATE_USER_CONFIGS = """
CREATE TABLE IF NOT EXISTS user_configs (
    phone_number    TEXT PRIMARY KEY,
    schedule_time   TEXT DEFAULT '20:00',
    timezone        TEXT DEFAULT 'Asia/Kolkata',
    pin_code        TEXT DEFAULT '0000',
    topics          JSONB NOT NULL DEFAULT '{}',
    channels        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_USER_HISTORY = """
CREATE TABLE IF NOT EXISTS user_history (
    phone_number    TEXT NOT NULL,
    category        TEXT NOT NULL,
    item            TEXT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (phone_number, category, item)
);
"""

_CREATE_USER_STATUS = """
CREATE TABLE IF NOT EXISTS user_status (
    phone_number    TEXT PRIMARY KEY,
    is_paired       BOOLEAN DEFAULT FALSE,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""


# ── Connection wrapper ──────────────────────────────────────────────────────────

class _ConnWrapper:
    """
    Thin wrapper over a psycopg2 connection that exposes the same
    `.execute()` / `.executemany()` interface as sqlite3.Connection.

    Rows are returned as RealDictRow (dict-like), matching the behaviour of
    sqlite3.Row when accessed by column name.
    """

    def __init__(self, conn: "psycopg2.extensions.connection") -> None:
        self._conn = conn
        self._cur = conn.cursor()

    def execute(self, sql: str, params=()):
        """Execute *sql* with *params* and return the cursor (supports .fetchone() / .fetchall())."""
        self._cur.execute(sql, params if params else None)
        return self._cur

    def executemany(self, sql: str, seq):
        """Execute *sql* for each param tuple in *seq*."""
        self._cur.executemany(sql, seq)
        return self._cur

    def _close(self) -> None:
        try:
            self._cur.close()
        finally:
            self._conn.close()


# ── Public API ──────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create tables and indexes if they don't exist.
    Called once at startup from main.py.
    Safe to call multiple times (all DDL uses IF NOT EXISTS).
    """
    with get_conn() as conn:
        conn.execute(_CREATE_SESSIONS)
        conn.execute(_CREATE_PERFORMANCE)
        conn.execute(_CREATE_USER_CONFIGS)
        conn.execute(_CREATE_USER_HISTORY)
        conn.execute(_CREATE_USER_STATUS)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_phone_reply "
            "ON sessions(phone_number, awaiting_reply)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_perf_phone_topic "
            "ON performance_scores(phone_number, topic)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_perf_answered_at "
            "ON performance_scores(answered_at)"
        )

    logger.info("✅ CoachDB initialised (PostgreSQL)")


@contextmanager
def get_conn():
    """
    Thread-safe PostgreSQL connection context manager.

    Commits on clean exit, rolls back on exception, always closes.
    Yields a _ConnWrapper whose .execute() returns a RealDictCursor so rows
    can be accessed by column name (e.g. row["topic"]).
    """
    raw_conn = psycopg2.connect(
        settings.get_database_url(),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    wrapper = _ConnWrapper(raw_conn)
    try:
        yield wrapper
        raw_conn.commit()
    except Exception as exc:
        raw_conn.rollback()
        logger.error(f"DB transaction rolled back: {exc}")
        raise
    finally:
        wrapper._close()
