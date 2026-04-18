# -*- coding: utf-8 -*-
"""
tests/test_integration_coach_loop.py
--------------------------------------
Integration tests for the end-to-end coach loop (PostgreSQL backend):
  Session → Score → Performance → Weak Topics → Weekly Report

These tests wire SessionManager + PerformanceTracker together against
a shared PostgreSQL test DB to verify the full flow works as one.

No LLM calls, no WhatsApp — fully offline.
"""

import json
import os
import pytest
import asyncio
import psycopg2
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


from src.core.sys_config import settings

# ── Fixture ────────────────────────────────────────────────────────────────────

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


PHONE = "919123456789"
QUESTION = "Design a rate limiter for 10M requests/day."
TOPIC = "System Design"


# ── Full Loop: Question → Reply → Score → Performance ──────────────────────────

class TestFullCoachLoop:

    def test_session_set_and_retrieved(self, isolated_db):
        """Bot sends question → session stored → can be retrieved."""
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        session = SessionManager.get_active_session(PHONE)
        assert session is not None
        assert session["question"] == QUESTION
        assert session["topic"] == TOPIC

    def test_score_recorded_after_reply(self, isolated_db):
        """After user replies and answer is evaluated, score is stored."""
        from src.core.session import SessionManager
        from src.core.performance import PerformanceTracker

        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        session = SessionManager.get_active_session(PHONE)

        eval_result = {"score": 7, "feedback": "Good.", "weak_aspects": ["token bucket"]}

        PerformanceTracker.record_score(
            PHONE, session["topic"],
            eval_result["score"], eval_result["weak_aspects"], eval_result["feedback"]
        )
        SessionManager.clear_session(session["id"])

        # Verify session cleared
        assert SessionManager.get_active_session(PHONE) is None

        # Verify score persisted
        summary = PerformanceTracker.get_weekly_summary(PHONE)
        assert len(summary) == 1
        assert summary[0]["topic"] == TOPIC
        assert float(summary[0]["avg_score"]) == 7.0

    def test_weak_topic_detection_after_bad_answers(self, isolated_db):
        """Low scores on a topic should surface it in weak topics."""
        from src.core.performance import PerformanceTracker
        from src.core.db import get_conn

        for score in [3, 4, 2]:
            answered = datetime.now(timezone.utc).isoformat()
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO performance_scores "
                    "(phone_number, topic, score, weak_aspects, feedback, answered_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (PHONE, "Kafka", score, json.dumps(["DLQ"]), "ok", answered)
                )

        weak = PerformanceTracker.get_weak_topics(PHONE, threshold=6)
        assert "Kafka" in weak

    def test_strong_performance_not_flagged_weak(self, isolated_db):
        from src.core.performance import PerformanceTracker
        from src.core.db import get_conn

        for score in [8, 9, 7]:
            answered = datetime.now(timezone.utc).isoformat()
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO performance_scores "
                    "(phone_number, topic, score, weak_aspects, feedback, answered_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (PHONE, "Redis", score, json.dumps([]), "ok", answered)
                )

        weak = PerformanceTracker.get_weak_topics(PHONE, threshold=6)
        assert "Redis" not in weak

    def test_stale_session_cleared_on_new_day(self, isolated_db):
        """Calling clear_all_stale (new daily cycle start) wipes unanswered session."""
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        SessionManager.clear_all_stale(PHONE)
        assert SessionManager.get_active_session(PHONE) is None

    def test_weekly_report_format_data(self, isolated_db):
        """Weekly summary returns correct structure for report formatting."""
        from src.core.performance import PerformanceTracker
        from src.core.db import get_conn

        topics_data = [
            ("Kafka", 5),
            ("Kafka", 7),
            ("Redis", 9),
        ]
        for topic, score in topics_data:
            answered = datetime.now(timezone.utc).isoformat()
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO performance_scores "
                    "(phone_number, topic, score, weak_aspects, feedback, answered_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (PHONE, topic, score, json.dumps([]), "ok", answered)
                )

        summary = PerformanceTracker.get_weekly_summary(PHONE)
        topics_in_summary = {r["topic"] for r in summary}
        assert "Kafka" in topics_in_summary
        assert "Redis" in topics_in_summary

        kafka_row = next(r for r in summary if r["topic"] == "Kafka")
        assert float(kafka_row["avg_score"]) == 6.0
        assert kafka_row["attempts"] == 2


# ── Scheduler handle_incoming mock test ────────────────────────────────────────

class TestHandleIncoming:
    """
    Tests for InterviewScheduler.handle_incoming()
    WhatsApp client is fully mocked — no real connection needed.
    """

    def _build_fake_message(self, phone: str, text: str):
        """Build a fake neonize MessageEv-like object."""
        msg = MagicMock()
        msg.Info.MessageSource.IsFromMe = True
        chat_mock = MagicMock()
        chat_mock.User = phone
        msg.Info.MessageSource.Chat = chat_mock
        msg.Message.conversation = text
        msg.Message.extendedTextMessage = MagicMock()
        msg.Message.extendedTextMessage.text = ""
        return msg

    def _build_scheduler(self, isolated_db, eval_result: dict):
        """Build an InterviewScheduler with all external deps mocked."""
        with patch("src.content.agent.LLMProvider") as MockLLM, \
             patch("src.content.agent.UserHistoryManager") as MockHist, \
             patch("src.scheduling.scheduler.ChannelSender"), \
             patch("src.scheduling.scheduler.ConfigManager"):

            MockLLM.return_value.generate_response = AsyncMock(return_value="")
            MockLLM.return_value.generate_image = AsyncMock(return_value="")
            MockHist.return_value.get_history = MagicMock(return_value=[])
            MockHist.return_value.add_to_history = MagicMock()

            from src.content.agent import InterviewAgent
            from src.scheduling.scheduler import InterviewScheduler

            agent = InterviewAgent(phone_number=PHONE)
            agent.evaluate_answer = AsyncMock(return_value=eval_result)

            wa = MagicMock()
            wa.send_message = AsyncMock()
            wa.connected = True

            scheduler = InterviewScheduler.__new__(InterviewScheduler)
            scheduler.agent = agent
            scheduler.whatsapp = wa
            scheduler.phone_number = PHONE

            config_mock = MagicMock()
            config_mock.channels.whatsapp_target = PHONE
            scheduler.config = config_mock

            return scheduler

    def run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_no_session_does_not_send_feedback(self, isolated_db):
        """If no active session, incoming message is silently ignored."""
        eval_result = {"score": 7, "feedback": "Good!", "weak_aspects": []}
        scheduler = self._build_scheduler(isolated_db, eval_result)
        msg = self._build_fake_message(PHONE, "My answer to nothing")

        self.run(scheduler.handle_incoming(None, msg))
        scheduler.whatsapp.send_message.assert_called_once()
        call_arg = scheduler.whatsapp.send_message.call_args[0][0]
        assert "an active question pending" in call_arg.lower()

    def test_active_session_triggers_feedback(self, isolated_db):
        """With active session, valid reply should trigger send_message."""
        from src.core.session import SessionManager
        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        eval_result = {"score": 8, "feedback": "Excellent!", "weak_aspects": []}
        scheduler = self._build_scheduler(isolated_db, eval_result)
        msg = self._build_fake_message(PHONE, "Detailed answer here.")

        self.run(scheduler.handle_incoming(None, msg))
        scheduler.whatsapp.send_message.assert_called_once()

    def test_score_persisted_to_db(self, isolated_db):
        """Score should be in performance_scores after handling reply."""
        from src.core.session import SessionManager
        from src.core.performance import PerformanceTracker

        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        eval_result = {"score": 6, "feedback": "Decent.", "weak_aspects": ["latency"]}
        scheduler = self._build_scheduler(isolated_db, eval_result)
        msg = self._build_fake_message(PHONE, "My answer.")

        self.run(scheduler.handle_incoming(None, msg))

        summary = PerformanceTracker.get_weekly_summary(PHONE)
        assert len(summary) == 1
        assert float(summary[0]["avg_score"]) == 6.0

    def test_session_cleared_after_scoring(self, isolated_db):
        """Session must be cleared so next reply is not double-scored."""
        from src.core.session import SessionManager

        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        eval_result = {"score": 7, "feedback": "Good!", "weak_aspects": []}
        scheduler = self._build_scheduler(isolated_db, eval_result)
        msg = self._build_fake_message(PHONE, "My answer.")

        self.run(scheduler.handle_incoming(None, msg))
        assert SessionManager.get_active_session(PHONE) is None

    def test_empty_message_ignored(self, isolated_db):
        """Empty / whitespace-only message must be silently ignored."""
        from src.core.session import SessionManager

        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        eval_result = {"score": 7, "feedback": "Good!", "weak_aspects": []}
        scheduler = self._build_scheduler(isolated_db, eval_result)
        msg = self._build_fake_message(PHONE, "   ")

        self.run(scheduler.handle_incoming(None, msg))
        scheduler.whatsapp.send_message.assert_not_called()

    def test_feedback_contains_score(self, isolated_db):
        """The feedback message sent to user must include the score."""
        from src.core.session import SessionManager

        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        eval_result = {"score": 5, "feedback": "Needs improvement.", "weak_aspects": ["retry"]}
        scheduler = self._build_scheduler(isolated_db, eval_result)
        msg = self._build_fake_message(PHONE, "My answer.")

        self.run(scheduler.handle_incoming(None, msg))
        call_args = scheduler.whatsapp.send_message.call_args[0][0]
        assert "5" in call_args

    def test_weak_aspects_included_in_feedback(self, isolated_db):
        """If weak_aspects present, they should appear in the feedback message."""
        from src.core.session import SessionManager

        SessionManager.set_active_question(PHONE, QUESTION, TOPIC)
        eval_result = {
            "score": 4,
            "feedback": "Weak answer.",
            "weak_aspects": ["token bucket", "sliding window"]
        }
        scheduler = self._build_scheduler(isolated_db, eval_result)
        msg = self._build_fake_message(PHONE, "My answer.")

        self.run(scheduler.handle_incoming(None, msg))
        call_args = scheduler.whatsapp.send_message.call_args[0][0]
        assert "token bucket" in call_args
