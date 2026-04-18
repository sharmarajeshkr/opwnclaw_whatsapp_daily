# -*- coding: utf-8 -*-
"""
tests/test_session.py
---------------------
Tests for src/core/session.py (SessionManager) — PostgreSQL backend.

Covers:
  - set_active_question: inserts correct row
  - get_active_session: returns dict when session exists
  - get_active_session: returns None when no session
  - get_active_session: returns None after session is cleared
  - clear_session: sets awaiting_reply=0 for the specific session ID
  - clear_all_stale: marks all pending sessions done for the phone
  - set_active_question enqueues multiple sessions (FIFO queue)
  - Isolation: two different phones have independent sessions
"""

import os
import pytest
import psycopg2
import psycopg2.extras


from src.core.sys_config import settings

# ── Fixture: temp DB + init ────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db():
    settings.POSTGRES_DB = "openclaw_test"

    from src.core.db import init_db
    init_db()
    dsn = settings.get_database_url()
    yield dsn

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE sessions, performance_scores RESTART IDENTITY CASCADE")
    cur.close()
    conn.close()


PHONE = "919876543210"
PHONE2 = "919000000001"
QUESTION = "Explain Kafka consumer group rebalancing."
TOPIC = "Kafka"


def _fetch_sessions(dsn: str, phone: str) -> list:
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE phone_number = %s ORDER BY sent_at ASC", (phone,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# ── set_active_question ────────────────────────────────────────────────────────

class TestSetActiveQuestion:
    def test_inserts_row(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        rows = _fetch_sessions(isolated_db, PHONE)
        assert len(rows) == 1

    def test_awaiting_reply_is_1(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        rows = _fetch_sessions(isolated_db, PHONE)
        assert rows[0]["awaiting_reply"] == 1

    def test_enqueues_multiple_sessions(self, isolated_db):
        """Queue Model — multiple sessions can pend per phone."""
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, "Q1", "Kafka")
        SessionManager.set_active_question(PHONE, "Q2", "Redis")
        rows = _fetch_sessions(isolated_db, PHONE)
        assert len(rows) == 2
        assert rows[0]["topic"] == "Kafka"
        assert rows[1]["topic"] == "Redis"

    def test_stored_values_correct(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        rows = _fetch_sessions(isolated_db, PHONE)
        assert rows[0]["question"] == QUESTION
        assert rows[0]["topic"] == TOPIC


# ── get_active_session ─────────────────────────────────────────────────────────

class TestGetActiveSession:
    def test_returns_dict_when_active(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        result = SessionManager.get_active_session(PHONE)
        assert result is not None
        assert isinstance(result, dict)

    def test_contains_expected_keys(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        result = SessionManager.get_active_session(PHONE)
        assert "id" in result
        assert "question" in result
        assert "topic" in result
        assert "sent_at" in result

    def test_correct_values_returned(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        result = SessionManager.get_active_session(PHONE)
        assert result["question"] == QUESTION
        assert result["topic"] == TOPIC

    def test_returns_none_when_no_session(self, isolated_db):
        from src.core.session import SessionManager
        result = SessionManager.get_active_session("9100000000")
        assert result is None

    def test_returns_none_after_clear(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        session = SessionManager.get_active_session(PHONE)
        SessionManager.clear_session(session["id"])
        result = SessionManager.get_active_session(PHONE)
        assert result is None


# ── clear_session ──────────────────────────────────────────────────────────────

class TestClearSession:
    def test_sets_awaiting_reply_to_zero(self, isolated_db):
        from src.core.session import SessionManager
        from src.core.db import get_conn
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        session = SessionManager.get_active_session(PHONE)
        SessionManager.clear_session(session["id"])
        with get_conn() as conn:
            row = conn.execute(
                "SELECT awaiting_reply FROM sessions WHERE id = %s", (session["id"],)
            ).fetchone()
        assert row["awaiting_reply"] == 0

    def test_clear_nonexistent_does_not_raise(self, isolated_db):
        """Clearing a session that doesn't exist should not raise."""
        from src.core.session import SessionManager
        SessionManager.clear_session(999999)  # should not raise


# ── clear_all_stale ────────────────────────────────────────────────────────────

class TestClearAllStale:
    def test_clears_pending_session(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        SessionManager.clear_all_stale(PHONE)
        result = SessionManager.get_active_session(PHONE)
        assert result is None

    def test_does_not_affect_other_phone(self, isolated_db):
        """Clearing stale for PHONE must not touch PHONE2's session."""
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        SessionManager.set_active_question(PHONE2, "Q2", "Redis")
        SessionManager.clear_all_stale(PHONE)
        result = SessionManager.get_active_session(PHONE2)
        assert result is not None


# ── Multi-user isolation ───────────────────────────────────────────────────────

class TestMultiUserIsolation:
    def test_two_phones_independent(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, "Q-Kafka", "Kafka")
        SessionManager.set_active_question(PHONE2, "Q-Redis", "Redis")

        s1 = SessionManager.get_active_session(PHONE)
        s2 = SessionManager.get_active_session(PHONE2)

        assert s1["topic"] == "Kafka"
        assert s2["topic"] == "Redis"

    def test_clear_one_leaves_other_intact(self, isolated_db):
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, "Q-Kafka", "Kafka")
        SessionManager.set_active_question(PHONE2, "Q-Redis", "Redis")
        s1 = SessionManager.get_active_session(PHONE)
        SessionManager.clear_session(s1["id"])

        assert SessionManager.get_active_session(PHONE) is None
        assert SessionManager.get_active_session(PHONE2) is not None
