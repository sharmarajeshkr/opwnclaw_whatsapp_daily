"""
performance.py
--------------
Manages per-user interview performance data stored in the `performance_scores`
table of coach.db.

Responsibilities:
 - Record every scored answer (topic, score, weak_aspects, feedback)
 - Identify weak topics for adaptive scheduling (avg score < threshold)
 - Generate weekly/all-time summary stats for the weekly report
"""

import json
from datetime import datetime, timezone
from src.core.db import get_conn
from src.core.logger import get_logger

logger = get_logger("PerformanceTracker")

# Topics with avg score below this are considered "weak"
WEAK_SCORE_THRESHOLD = 6
# Look-back window for weak topic detection
WEAK_LOOKBACK_DAYS = 30


class PerformanceTracker:
    """Read/write wrapper around the `performance_scores` table."""

    @staticmethod
    def record_score(
        phone: str,
        topic: str,
        score: int,
        weak_aspects: list[str],
        feedback: str,
    ) -> None:
        """
        Persist a single scored answer to the DB.

        Args:
            phone:         User's phone number (digits only)
            topic:         Topic label (e.g. "Kafka", "Circuit Breaker")
            score:         Integer 0–10
            weak_aspects:  List of concept strings the user missed
            feedback:      LLM feedback text (stored for audit / future use)
        """
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO performance_scores
                    (phone_number, topic, score, weak_aspects, feedback, answered_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (phone, topic, score, json.dumps(weak_aspects), feedback, now),
            )
        logger.info(f"[{phone}] Score recorded — topic='{topic}' score={score}/10")

    @staticmethod
    def get_weak_topics(
        phone: str,
        threshold: int = WEAK_SCORE_THRESHOLD,
        lookback_days: int = WEAK_LOOKBACK_DAYS,
    ) -> list[str]:
        """
        Return topics where the user's average score is below `threshold`
        in the last `lookback_days` days, sorted weakest-first.

        Returns:
            List of topic name strings (may be empty if no weak topics).
        """
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT topic, AVG(score) AS avg_score
                FROM performance_scores
                WHERE phone_number = %s
                  AND answered_at::timestamptz >= NOW() - INTERVAL %s
                GROUP BY topic
                HAVING AVG(score) < %s
                ORDER BY AVG(score) ASC
                """,
                (phone, f"{lookback_days} days", threshold),
            ).fetchall()
        topics = [row["topic"] for row in rows]
        if topics:
            logger.info(f"[{phone}] Weak topics detected: {topics}")
        return topics

    @staticmethod
    def get_weekly_summary(phone: str) -> list[dict]:
        """
        Return per-topic statistics for the last 7 days.

        Returns:
            List of dicts with keys:
              {topic, avg_score, attempts, min_score, max_score}
            Ordered weakest-first.
        """
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    topic,
                    ROUND(AVG(score)::numeric, 1)  AS avg_score,
                    COUNT(*)                        AS attempts,
                    MIN(score)                      AS min_score,
                    MAX(score)                      AS max_score
                FROM performance_scores
                WHERE phone_number = %s
                  AND answered_at::timestamptz >= NOW() - INTERVAL '7 days'
                GROUP BY topic
                ORDER BY AVG(score) ASC
                """,
                (phone,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_all_time_summary(phone: str) -> list[dict]:
        """
        Return per-topic all-time statistics.
        Useful for dashboard display or deep reporting.
        """
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    topic,
                    ROUND(AVG(score)::numeric, 1)  AS avg_score,
                    COUNT(*)                        AS attempts,
                    MIN(score)                      AS min_score,
                    MAX(score)                      AS max_score
                FROM performance_scores
                WHERE phone_number = %s
                GROUP BY topic
                ORDER BY AVG(score) ASC
                """,
                (phone,),
            ).fetchall()
        return [dict(row) for row in rows]
