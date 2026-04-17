"""
session.py
----------
Manages per-user session state stored in the `sessions` table of coach.db.

A "session" represents: "Bot sent this question to this user and is waiting
for a reply to score." One active session per user at a time.
"""

from datetime import datetime, timezone
from src.core.db import get_conn
from src.core.logger import get_logger

logger = get_logger("SessionManager")


class SessionManager:
    """CRUD wrapper around the `sessions` table."""

    @staticmethod
    def set_active_question(phone: str, question: str, topic: str) -> None:
        """
        Record a newly sent question for a user.
        Uses INSERT OR REPLACE so previous unanswered sessions are overwritten
        (one active question per user at a time).

        Args:
            phone:    User's phone number (digits only, no +)
            question: The exact question text sent to the user
            topic:    Topic label used later for performance tracking
        """
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                    (phone_number, question, topic, sent_at, awaiting_reply)
                VALUES (?, ?, ?, ?, 1)
                """,
                (phone, question, topic, now),
            )
        logger.debug(f"[{phone}] Session set — topic='{topic}'")

    @staticmethod
    def get_active_session(phone: str) -> dict | None:
        """
        Return the current unanswered session for a user, or None.

        Returns:
            dict with keys {question, topic, sent_at} or None
        """
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT question, topic, sent_at
                FROM sessions
                WHERE phone_number = ? AND awaiting_reply = 1
                """,
                (phone,),
            ).fetchone()
        if row:
            logger.debug(f"[{phone}] Active session found — topic='{row['topic']}'")
            return dict(row)
        return None

    @staticmethod
    def clear_session(phone: str) -> None:
        """
        Mark a session as answered (awaiting_reply = 0).
        Called after the answer has been scored and feedback sent.
        """
        with get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET awaiting_reply = 0 WHERE phone_number = ?",
                (phone,),
            )
        logger.debug(f"[{phone}] Session cleared.")

    @staticmethod
    def clear_all_stale(phone: str) -> None:
        """
        Force-clear any pending session for a user.
        Called at the start of each daily_task to avoid a stale session
        blocking scoring of the new day's question.
        """
        with get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET awaiting_reply = 0 WHERE phone_number = ?",
                (phone,),
            )
        logger.debug(f"[{phone}] Stale sessions cleared before new daily cycle.")
