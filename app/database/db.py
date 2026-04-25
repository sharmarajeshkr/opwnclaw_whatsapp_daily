"""
app/database/db.py
------------------
Central PostgreSQL connection manager.
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from app.core.logging import get_logger, log_duration
from app.core.config import settings

logger = get_logger("CoachDB")


# ── Schema DDL ──────────────────────────────────────────────────────────────────

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id              SERIAL PRIMARY KEY,
    phone_number    TEXT NOT NULL,
    question        TEXT NOT NULL,
    topic           TEXT NOT NULL,
    sent_at         TEXT NOT NULL,
    awaiting_reply  INTEGER DEFAULT 1,
    follow_up_count INTEGER DEFAULT 0
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
    name            TEXT DEFAULT '',
    schedule_time   TEXT DEFAULT '20:00',
    timezone        TEXT DEFAULT 'Asia/Kolkata',
    pin_code        TEXT DEFAULT '0000',
    topics          JSONB NOT NULL DEFAULT '{}',
    channels        JSONB NOT NULL DEFAULT '{}',
    level           TEXT DEFAULT 'Beginner',
    skill_profile   JSONB NOT NULL DEFAULT '{"backend": 5, "system_design": 5, "ai": 5}',
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
    is_active       BOOLEAN DEFAULT TRUE,
    current_streak  INTEGER DEFAULT 0,
    last_reply_at   TIMESTAMP WITH TIME ZONE,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_LLM_CACHE = """
CREATE TABLE IF NOT EXISTS llm_cache (
    prompt_hash     TEXT PRIMARY KEY,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_text     TEXT,
    response_text   TEXT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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
        conn.execute(_CREATE_LLM_CACHE)
        conn.execute("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS skill_profile JSONB NOT NULL DEFAULT '{\"backend\": 5, \"system_design\": 5, \"ai\": 5}'")
        conn.execute("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS level TEXT DEFAULT 'Beginner'")
        conn.execute("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS name TEXT DEFAULT ''")
        conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS follow_up_count INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE user_status ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        conn.execute("ALTER TABLE user_status ADD COLUMN IF NOT EXISTS current_streak INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE user_status ADD COLUMN IF NOT EXISTS last_reply_at TIMESTAMP WITH TIME ZONE")
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
@log_duration(logger)
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
