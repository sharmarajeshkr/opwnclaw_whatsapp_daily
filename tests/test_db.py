# -*- coding: utf-8 -*-
"""
tests/test_db.py
----------------
Tests for src/core/db.py

Covers:
  - init_db() creates correct tables and indexes in a temp DB
  - get_conn() context manager: commit on success, rollback on error
  - WAL mode is enabled
  - Idempotency: calling init_db() twice does not error
"""

import sqlite3
import pytest
import os
import tempfile


# ── Fixture: isolated temp DB per test ────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """
    Redirect DB_PATH to a fresh temp file for every test.
    No test should ever touch the real data/coach.db.
    """
    import src.core.db as db_module
    temp_db = str(tmp_path / "test_coach.db")
    monkeypatch.setattr(db_module, "DB_PATH", temp_db)
    yield temp_db


# ── init_db ────────────────────────────────────────────────────────────────────

class TestInitDb:
    def test_creates_sessions_table(self, isolated_db):
        from src.core.db import init_db
        init_db()
        conn = sqlite3.connect(isolated_db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "sessions" in tables

    def test_creates_performance_scores_table(self, isolated_db):
        from src.core.db import init_db
        init_db()
        conn = sqlite3.connect(isolated_db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "performance_scores" in tables

    def test_creates_required_indexes(self, isolated_db):
        from src.core.db import init_db
        init_db()
        conn = sqlite3.connect(isolated_db)
        indexes = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()]
        conn.close()
        assert "idx_perf_phone_topic" in indexes
        assert "idx_perf_answered_at" in indexes

    def test_idempotent_double_call(self, isolated_db):
        """Calling init_db() twice should not raise any error."""
        from src.core.db import init_db
        init_db()
        init_db()  # should NOT raise

    def test_sessions_schema(self, isolated_db):
        """Verify sessions table has expected columns."""
        from src.core.db import init_db
        init_db()
        conn = sqlite3.connect(isolated_db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        conn.close()
        assert {"phone_number", "question", "topic", "sent_at", "awaiting_reply"}.issubset(cols)

    def test_performance_scores_schema(self, isolated_db):
        """Verify performance_scores table has expected columns."""
        from src.core.db import init_db
        init_db()
        conn = sqlite3.connect(isolated_db)
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(performance_scores)"
        ).fetchall()}
        conn.close()
        assert {
            "id", "phone_number", "topic", "score",
            "weak_aspects", "feedback", "answered_at"
        }.issubset(cols)

    def test_wal_mode_enabled(self, isolated_db):
        from src.core.db import init_db, get_conn
        init_db()
        with get_conn() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


# ── get_conn ───────────────────────────────────────────────────────────────────

class TestGetConn:
    def test_commit_on_success(self, isolated_db):
        from src.core.db import init_db, get_conn
        init_db()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions(phone_number, question, topic, sent_at) "
                "VALUES ('91111', 'Q?', 'Kafka', '2026-01-01T10:00:00')"
            )
        # Verify row persisted in a new connection
        conn2 = sqlite3.connect(isolated_db)
        row = conn2.execute(
            "SELECT phone_number FROM sessions WHERE phone_number='91111'"
        ).fetchone()
        conn2.close()
        assert row is not None

    def test_rollback_on_exception(self, isolated_db):
        from src.core.db import init_db, get_conn
        init_db()
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO sessions(phone_number, question, topic, sent_at) "
                    "VALUES ('91222', 'Q?', 'Kafka', '2026-01-01T10:00:00')"
                )
                raise ValueError("Simulated failure")
        except ValueError:
            pass

        conn2 = sqlite3.connect(isolated_db)
        row = conn2.execute(
            "SELECT phone_number FROM sessions WHERE phone_number='91222'"
        ).fetchone()
        conn2.close()
        assert row is None, "Row should not exist after rollback"
