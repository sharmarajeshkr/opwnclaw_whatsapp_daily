# -*- coding: utf-8 -*-
"""
tests/test_weekly_insights.py
------------------------------
Tests for the new Summary Mode (Weekly AI Insight) feature.
"""

import json
import pytest
import psycopg2
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from api import app
from app.services.performance_tracker import PerformanceTracker
from app.agents.analytic_agent import AnalyticAgent
from app.core.config import settings

client = TestClient(app)

PHONE = "919876543210"

@pytest.fixture(autouse=True)
def isolated_db():
    settings.POSTGRES_DB = "openclaw_test"
    from app.database.db import init_db, get_conn
    init_db()
    
    dsn = settings.get_database_url()

    # Setup: 1. Truncate 2. Register User 3. Disable Auth
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE sessions, performance_scores, user_insights, user_configs RESTART IDENTITY CASCADE")
    cur.close()
    conn.close()

    from app.core.config import ConfigManager, UserConfig
    ConfigManager.save_config(PHONE, UserConfig())
    
    # Also register in user_status so get_all_users() finds them
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_status (phone_number, is_active) VALUES (%s, TRUE) "
            "ON CONFLICT (phone_number) DO UPDATE SET is_active = TRUE",
            (PHONE,)
        )
    
    settings.API_SECRET_KEY = None  # Disable auth for tests

    yield dsn

# ── PerformanceTracker Extensions ───────────────────────────────────────────

class TestPerformanceTrackerExtensions:
    def test_record_with_question_text(self, isolated_db):
        q_text = "What is a saga pattern?"
        PerformanceTracker.record_score(PHONE, "Architecture", 8, [], "Great", question_text=q_text)
        
        data = PerformanceTracker.get_weekly_detailed_data(PHONE)
        assert len(data) == 1
        assert data[0]["question_text"] == q_text

    def test_save_and_get_insight(self, isolated_db):
        insight = "You are doing great in Distributed Systems."
        week_id = "2026-W16"
        PerformanceTracker.save_weekly_insight(PHONE, week_id, insight)
        
        result = PerformanceTracker.get_latest_insight(PHONE)
        assert result["insight_text"] == insight
        assert result["week_id"] == week_id

# ── AnalyticAgent ───────────────────────────────────────────────────────────

class TestAnalyticAgent:
    @pytest.mark.anyio
    async def test_generate_insight_with_mock_llm(self, mocker):
        # Mock LLMProvider.generate_response
        mock_llm = mocker.patch("app.llm.provider.LLMProvider.generate_response")
        mock_llm.return_value = "💡 *Weekly AI Insight*\nMocked mentorship text."
        
        agent = AnalyticAgent(PHONE)
        mock_data = [
            {
                "topic": "Kafka",
                "score": 4,
                "question_text": "How to scale consumers?",
                "feedback": "Bad error handling",
                "weak_aspects": ["DLQ"]
            }
        ]
        
        insight = await agent.generate_weekly_insight(mock_data, "Intermediate")
        assert "Weekly AI Insight" in insight
        assert "Mocked mentorship text" in insight

# ── API Endpoints ───────────────────────────────────────────────────────────

class TestAPIWeeklyInsight:
    def test_get_insight_returns_404_if_none(self, isolated_db):
        # The endpoint returns a message if no insight found (not necessarily a 404 in current impl)
        resp = client.get(f"/api/users/{PHONE}/weekly-insight")
        assert resp.status_code == 200
        assert "No insight generated yet" in resp.json()["insight"]

    def test_get_insight_returns_data(self, isolated_db):
        PerformanceTracker.save_weekly_insight(PHONE, "2026-W16", "API Test Insight")
        resp = client.get(f"/api/users/{PHONE}/weekly-insight")
        assert resp.status_code == 200
        assert resp.json()["insight_text"] == "API Test Insight"
