"""
app/services/session_manager.py
-------------------------------
Manages per-user session state stored in the `sessions` table of PostgreSQL.

QUEUE MODEL (v2 — GAP-04 fix):
  Previously the table used phone_number as PRIMARY KEY, so INSERT OR REPLACE
  would overwrite the first deep-dive question the moment the second one was
  stored. Only the last question ever got scored.

  v2 treats the sessions table as a FIFO queue:
    - set_active_question()  → appends to the queue (plain INSERT)
    - get_active_session()   → returns the OLDEST pending row (ORDER BY sent_at ASC)
    - clear_session(id)      → marks exactly THAT row as answered (by its integer id)
    - clear_all_stale(phone) → clears ALL pending rows for a user (start of new cycle)

  Result: both daily deep-dive questions are independently stored and scored
  in arrival order. A user's second reply scores the second question, not the
  first one again.
"""

from datetime import datetime, timezone
from app.database.db import get_conn
from app.core.logging import get_logger

logger = get_logger("SessionManager")


class SessionManager:
    """CRUD wrapper around the `sessions` table (v2 queue model)."""

    @staticmethod
    def set_active_question(phone: str, question: str, topic: str) -> None:
        """
        Enqueue a newly sent question for a user.

        Unlike v1 (INSERT OR REPLACE), this is a plain INSERT that allows
        multiple questions to be pending simultaneously — e.g. the two
        deep-dive topics sent in one daily cycle.

        Args:
            phone:    User's phone number (digits only, no +)
            question: The exact question text sent to the user
            topic:    Topic label used later for performance tracking
        """
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                    (phone_number, question, topic, sent_at, awaiting_reply, follow_up_count)
                VALUES (%s, %s, %s, %s, 1, 0)
                """,
                (phone, question, topic, now),
            )
        logger.debug(f"[{phone}] Question enqueued — topic='{topic}'")

    @staticmethod
    def get_active_session(phone: str) -> dict | None:
        """
        Return the OLDEST unanswered question for a user (FIFO), or None.

        Returns:
            dict with keys {id, question, topic, sent_at} or None.
            The `id` field must be passed to clear_session() after scoring.
        """
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT id, question, topic, sent_at, follow_up_count
                FROM sessions
                WHERE phone_number = %s AND awaiting_reply = 1
                ORDER BY sent_at ASC
                LIMIT 1
                """,
                (phone,),
            ).fetchone()
        if row:
            logger.debug(
                f"[{phone}] Active session found — topic='{row['topic']}' id={row['id']}"
            )
            return dict(row)
        return None

    @staticmethod
    def clear_session(session_id: int) -> None:
        """
        Mark one specific question as answered by its database id.

        Called after the answer has been scored and feedback sent.
        Targeting by id (not phone) ensures only the question that was
        just scored is cleared, leaving any other queued questions intact.

        Args:
            session_id: The `id` value returned by get_active_session()
        """
        with get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET awaiting_reply = 0 WHERE id = %s",
                (session_id,),
            )
        logger.debug(f"Session id={session_id} cleared.")

    @staticmethod
    def update_session_with_follow_up(session_id: int, follow_up_question: str) -> None:
        """
        Replace the current question with a follow-up and increment the count.
        """
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE sessions 
                SET question = %s, follow_up_count = follow_up_count + 1 
                WHERE id = %s
                """,
                (follow_up_question, session_id),
            )
        logger.info(f"Session id={session_id} updated with follow-up question.")

    @staticmethod
    def clear_all_stale(phone: str) -> None:
        """
        Force-clear ALL pending questions for a user.

        Called at the start of each daily_task so that unanswered questions
        from the previous cycle do not linger into the next day's scoring.
        """
        with get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET awaiting_reply = 0 WHERE phone_number = %s",
                (phone,),
            )
        logger.debug(f"[{phone}] All stale sessions cleared before new daily cycle.")

    @staticmethod
    def pending_count(phone: str) -> int:
        """Return how many questions are currently waiting for a reply."""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM sessions "
                "WHERE phone_number = %s AND awaiting_reply = 1",
                (phone,),
            ).fetchone()
        return row["cnt"] if row else 0
