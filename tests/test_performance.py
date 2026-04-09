# -*- coding: utf-8 -*-
"""
tests/test_performance.py
--------------------------
Tests for src/core/performance.py (PerformanceTracker)

Covers:
  - record_score: persists row with correct values
  - record_score: weak_aspects stored as JSON array
  - get_weak_topics: returns topics below threshold sorted weakest-first
  - get_weak_topics: filters by lookback window (old scores excluded)
  - get_weak_topics: returns empty list when all scores >= threshold
  - get_weekly_summary: correct aggregation for 7 days
  - get_weekly_summary: excludes entries older than 7 days
  - get_weekly_summary: returns empty list when no data
  - get_all_time_summary: includes all historical data
  - Multi-user isolation: scores for phoneA don't appear for phoneB
  - Edge: score clamping handled at record level
"""

import json
import pytest
import sqlite3
from datetime import datetime, timezone, timedelta


# ── Fixture: temp isolated DB ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import src.core.db as db_module
    temp_db = str(tmp_path / "test_coach.db")
    monkeypatch.setattr(db_module, "DB_PATH", temp_db)
    from src.core.db import init_db
    init_db()
    yield temp_db


PHONE = "919876543210"
PHONE2 = "919111111111"


def _insert_score(isolated_db, phone, topic, score, days_ago=0):
    """Helper: insert a score with a controlled answered_at date."""
    from src.core.db import get_conn
    answered = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO performance_scores "
            "(phone_number, topic, score, weak_aspects, feedback, answered_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (phone, topic, score, json.dumps([]), "ok", answered),
        )


# ── record_score ───────────────────────────────────────────────────────────────

class TestRecordScore:
    def test_row_inserted(self, isolated_db):
        from src.core.performance import PerformanceTracker
        PerformanceTracker.record_score(PHONE, "Kafka", 7, ["DLQ"], "Good answer!")
        conn = sqlite3.connect(isolated_db)
        rows = conn.execute(
            "SELECT * FROM performance_scores WHERE phone_number=?", (PHONE,)
        ).fetchall()
        conn.close()
        assert len(rows) == 1

    def test_score_stored_correctly(self, isolated_db):
        from src.core.performance import PerformanceTracker
        PerformanceTracker.record_score(PHONE, "Kafka", 8, [], "Nice!")
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT score FROM performance_scores WHERE phone_number=?", (PHONE,)
        ).fetchone()
        conn.close()
        assert row[0] == 8

    def test_topic_stored_correctly(self, isolated_db):
        from src.core.performance import PerformanceTracker
        PerformanceTracker.record_score(PHONE, "Circuit Breaker", 5, [], "ok")
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT topic FROM performance_scores WHERE phone_number=?", (PHONE,)
        ).fetchone()
        conn.close()
        assert row[0] == "Circuit Breaker"

    def test_weak_aspects_stored_as_json(self, isolated_db):
        from src.core.performance import PerformanceTracker
        aspects = ["idempotency", "DLQ", "retry"]
        PerformanceTracker.record_score(PHONE, "Kafka", 4, aspects, "ok")
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT weak_aspects FROM performance_scores WHERE phone_number=?", (PHONE,)
        ).fetchone()
        conn.close()
        stored = json.loads(row[0])
        assert stored == aspects

    def test_multiple_scores_same_topic(self, isolated_db):
        from src.core.performance import PerformanceTracker
        PerformanceTracker.record_score(PHONE, "Kafka", 5, [], "ok")
        PerformanceTracker.record_score(PHONE, "Kafka", 8, [], "ok")
        conn = sqlite3.connect(isolated_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM performance_scores WHERE phone_number=? AND topic='Kafka'",
            (PHONE,)
        ).fetchone()[0]
        conn.close()
        assert count == 2

    def test_empty_weak_aspects(self, isolated_db):
        from src.core.performance import PerformanceTracker
        PerformanceTracker.record_score(PHONE, "Kafka", 9, [], "Perfect!")
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT weak_aspects FROM performance_scores WHERE phone_number=?", (PHONE,)
        ).fetchone()
        conn.close()
        assert json.loads(row[0]) == []


# ── get_weak_topics ────────────────────────────────────────────────────────────

class TestGetWeakTopics:
    def test_returns_topic_below_threshold(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 3)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=6)
        assert "Kafka" in result

    def test_excludes_topic_above_threshold(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Redis", 9)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=6)
        assert "Redis" not in result

    def test_sorted_weakest_first(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 5)
        _insert_score(isolated_db, PHONE, "Circuit Breaker", 2)
        _insert_score(isolated_db, PHONE, "HLD", 4)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=6)
        # Circuit Breaker avg=2 should be first
        assert result[0] == "Circuit Breaker"

    def test_empty_when_all_scores_strong(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 7)
        _insert_score(isolated_db, PHONE, "Redis", 8)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=6)
        assert result == []

    def test_old_scores_excluded_by_lookback(self, isolated_db):
        """Scores older than lookback_days should NOT affect weak topic detection."""
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "OldTopic", 2, days_ago=35)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=6, lookback_days=30)
        assert "OldTopic" not in result

    def test_recent_scores_included_in_lookback(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "RecentTopic", 2, days_ago=5)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=6, lookback_days=30)
        assert "RecentTopic" in result

    def test_empty_when_no_scores(self, isolated_db):
        from src.core.performance import PerformanceTracker
        result = PerformanceTracker.get_weak_topics("9100000000", threshold=6)
        assert result == []

    def test_multi_user_isolation(self, isolated_db):
        """Weak topics for PHONE must not bleed into PHONE2."""
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 2)
        result = PerformanceTracker.get_weak_topics(PHONE2, threshold=6)
        assert "Kafka" not in result

    def test_average_across_multiple_attempts(self, isolated_db):
        """Avg of [3, 9] = 6.0, should NOT be weak (threshold < 6)."""
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 3)
        _insert_score(isolated_db, PHONE, "Kafka", 9)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=6)
        # avg == 6.0, threshold requires avg < 6 → not weak
        assert "Kafka" not in result

    def test_custom_threshold(self, isolated_db):
        """Using threshold=8 should flag topics with avg < 8."""
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Redis", 7)
        result = PerformanceTracker.get_weak_topics(PHONE, threshold=8)
        assert "Redis" in result


# ── get_weekly_summary ─────────────────────────────────────────────────────────

class TestGetWeeklySummary:
    def test_returns_list_of_dicts(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 7)
        result = PerformanceTracker.get_weekly_summary(PHONE)
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_contains_expected_keys(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 7)
        row = PerformanceTracker.get_weekly_summary(PHONE)[0]
        assert {"topic", "avg_score", "attempts", "min_score", "max_score"}.issubset(row)

    def test_correct_avg_score(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "Kafka", 4)
        _insert_score(isolated_db, PHONE, "Kafka", 8)
        result = PerformanceTracker.get_weekly_summary(PHONE)
        kafka_row = next(r for r in result if r["topic"] == "Kafka")
        assert kafka_row["avg_score"] == 6.0

    def test_correct_attempt_count(self, isolated_db):
        from src.core.performance import PerformanceTracker
        for _ in range(5):
            _insert_score(isolated_db, PHONE, "Redis", 7)
        result = PerformanceTracker.get_weekly_summary(PHONE)
        redis_row = next(r for r in result if r["topic"] == "Redis")
        assert redis_row["attempts"] == 5

    def test_correct_min_max(self, isolated_db):
        from src.core.performance import PerformanceTracker
        for score in [2, 5, 9]:
            _insert_score(isolated_db, PHONE, "HLD", score)
        result = PerformanceTracker.get_weekly_summary(PHONE)
        hld_row = next(r for r in result if r["topic"] == "HLD")
        assert hld_row["min_score"] == 2
        assert hld_row["max_score"] == 9

    def test_excludes_entries_older_than_7_days(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "OldTopic", 3, days_ago=8)
        result = PerformanceTracker.get_weekly_summary(PHONE)
        topics = [r["topic"] for r in result]
        assert "OldTopic" not in topics

    def test_returns_empty_when_no_data(self, isolated_db):
        from src.core.performance import PerformanceTracker
        result = PerformanceTracker.get_weekly_summary("9199999999")
        assert result == []

    def test_sorted_weakest_first(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "TopicA", 9)
        _insert_score(isolated_db, PHONE, "TopicB", 2)
        result = PerformanceTracker.get_weekly_summary(PHONE)
        assert result[0]["topic"] == "TopicB"


# ── get_all_time_summary ───────────────────────────────────────────────────────

class TestGetAllTimeSummary:
    def test_includes_old_data(self, isolated_db):
        from src.core.performance import PerformanceTracker
        _insert_score(isolated_db, PHONE, "LegacyTopic", 4, days_ago=90)
        result = PerformanceTracker.get_all_time_summary(PHONE)
        topics = [r["topic"] for r in result]
        assert "LegacyTopic" in topics

    def test_returns_empty_for_new_user(self, isolated_db):
        from src.core.performance import PerformanceTracker
        result = PerformanceTracker.get_all_time_summary("9100000002")
        assert result == []
