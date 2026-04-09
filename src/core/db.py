import sqlite3
import os
from contextlib import contextmanager
from src.core.logger import get_logger

DB_PATH = os.path.join("data", "coach.db")
logger = get_logger("CoachDB")

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    phone_number    TEXT PRIMARY KEY,
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

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_perf_phone_topic
    ON performance_scores(phone_number, topic);

CREATE INDEX IF NOT EXISTS idx_perf_answered_at
    ON performance_scores(answered_at);
"""


def init_db():
    """Create tables and indexes if they don't exist. Called once at startup."""
    os.makedirs("data", exist_ok=True)
    with get_conn() as conn:
        conn.execute(_CREATE_SESSIONS)
        conn.execute(_CREATE_PERFORMANCE)
        conn.executescript(_CREATE_INDEXES)
    logger.info(f"✅ CoachDB initialised at '{DB_PATH}'")


@contextmanager
def get_conn():
    """
    Thread-safe SQLite connection context manager.
    Commits on clean exit, rolls back on exception, always closes.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
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
