"""
src/core/db.py
--------------
Central SQLite connection manager for coach.db.

Schema v2 (GAP-04 fix):
  - `sessions` now uses an autoincrement `id` as PRIMARY KEY, allowing
    multiple pending questions per user (FIFO queue model).
    Migration from v1 (phone_number PRIMARY KEY) is handled automatically
    in init_db() so existing databases are upgraded transparently.
  - `performance_scores` unchanged.
"""
import sqlite3
import os
from contextlib import contextmanager
from src.core.logger import get_logger

DB_PATH = os.path.join("data", "coach.db")
logger = get_logger("CoachDB")

# ── Schema DDL ─────────────────────────────────────────────────────────────────

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number    TEXT NOT NULL,
    question        TEXT NOT NULL,
    topic           TEXT NOT NULL,
    sent_at         TEXT NOT NULL,
    awaiting_reply  INTEGER DEFAULT 1
);
"""

_CREATE_PERFORMANCE = """
CREATE TABLE IF NOT EXISTS performance_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number    TEXT NOT NULL,
    topic           TEXT NOT NULL,
    score           INTEGER NOT NULL,
    weak_aspects    TEXT,
    feedback        TEXT,
    answered_at     TEXT NOT NULL
);
"""


# ── Migration ──────────────────────────────────────────────────────────────────

def _migrate_sessions_v2(conn: sqlite3.Connection) -> None:
    """
    One-time migration: v1 used phone_number as PRIMARY KEY (single row per user).
    v2 uses an autoincrement id so multiple questions can queue concurrently.

    Safe to call even if the table doesn't exist yet or is already on v2.
    """
    # Check which tables exist
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "sessions" not in tables:
        return  # Fresh install — CREATE TABLE IF NOT EXISTS will handle it

    # Check whether the v2 `id` column is already present
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "id" in cols:
        return  # Already on v2 — nothing to do

    logger.info("🔄 Migrating sessions table → v2 queue schema …")

    old_rows = conn.execute(
        "SELECT phone_number, question, topic, sent_at, awaiting_reply FROM sessions"
    ).fetchall()

    conn.execute("DROP TABLE sessions")
    conn.execute(
        """
        CREATE TABLE sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number    TEXT NOT NULL,
            question        TEXT NOT NULL,
            topic           TEXT NOT NULL,
            sent_at         TEXT NOT NULL,
            awaiting_reply  INTEGER DEFAULT 1
        )
        """
    )
    if old_rows:
        conn.executemany(
            """
            INSERT INTO sessions
                (phone_number, question, topic, sent_at, awaiting_reply)
            VALUES (?, ?, ?, ?, ?)
            """,
            [tuple(row) for row in old_rows],
        )

    logger.info(f"✅ Sessions v2 migration complete — {len(old_rows)} row(s) migrated.")


# ── Public API ─────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create tables and indexes if they don't exist, and run any pending
    schema migrations. Called once at startup from main.py.
    """
    os.makedirs("data", exist_ok=True)
    with get_conn() as conn:
        # 1. Migrate existing sessions table to v2 if needed
        _migrate_sessions_v2(conn)

        # 2. Create tables (IF NOT EXISTS — idempotent)
        conn.execute(_CREATE_SESSIONS)
        conn.execute(_CREATE_PERFORMANCE)

        # 3. Create indexes individually (executescript auto-commits,
        #    so we use separate execute() calls to stay in the transaction)
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

    logger.info(f"✅ CoachDB initialised at '{DB_PATH}'")


@contextmanager
def get_conn():
    """
    Thread-safe SQLite connection context manager.
    Commits on clean exit, rolls back on exception, always closes.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode: better concurrent read performance across multiple bot tasks
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error(f"DB transaction rolled back: {exc}")
        raise
    finally:
        conn.close()
