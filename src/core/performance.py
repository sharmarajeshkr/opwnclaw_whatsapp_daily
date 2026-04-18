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

    @staticmethod
    def update_streak(phone: str) -> int:
        """
        Increment or reset the daily streak based on the last reply time.
        Returns the new streak count.
        """
        now = datetime.now(timezone.utc)
        with get_conn() as conn:
            # 1. Fetch current status
            status = conn.execute(
                "SELECT current_streak, last_reply_at FROM user_status WHERE phone_number = %s",
                (phone,)
            ).fetchone()
            
            if not status:
                # Initialize if not exists
                conn.execute(
                    "INSERT INTO user_status (phone_number, current_streak, last_reply_at, is_paired) VALUES (%s, 1, %s, TRUE)",
                    (phone, now)
                )
                return 1
            
            last_reply = status["last_reply_at"]
            curr_streak = status["current_streak"] or 0
            
            if last_reply:
                # Ensure we compare in UTC
                if last_reply.tzinfo is not None:
                    last_reply = last_reply.astimezone(timezone.utc)
                else:
                    last_reply = last_reply.replace(tzinfo=timezone.utc)
                
                delta = now.date() - last_reply.date()
                if delta.days == 0:
                    # Already replied today
                    return curr_streak
                elif delta.days == 1:
                    # Consecutive day
                    new_streak = curr_streak + 1
                else:
                    # Missed a day
                    new_streak = 1
            else:
                new_streak = 1
                
            conn.execute(
                "UPDATE user_status SET current_streak = %s, last_reply_at = %s WHERE phone_number = %s",
                (new_streak, now, phone)
            )
            return new_streak

    @staticmethod
    def get_leaderboard(limit: int = 5) -> list[dict]:
        """
        Aggregate all users and rank them by weighted weekly score.
        """
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT 
                    p.phone_number,
                    s.current_streak,
                    ROUND(AVG(p.score)::numeric, 1) as avg_score,
                    COUNT(*) as weekly_attempts
                FROM performance_scores p
                LEFT JOIN user_status s ON p.phone_number = s.phone_number
                WHERE p.answered_at::timestamptz >= NOW() - INTERVAL '7 days'
                GROUP BY p.phone_number, s.current_streak
                ORDER BY avg_score DESC, weekly_attempts DESC
                LIMIT %s
                """,
                (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
