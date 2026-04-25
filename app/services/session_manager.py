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
        Record a new question sent to a user.
        """
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions 
                    (phone_number, question, topic, sent_at, awaiting_reply, follow_up_count)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 1, 0)
                """,
                (phone, question, topic),
            )
        logger.debug(f"[{phone}] Question enqueued — topic='{topic}'")

    @staticmethod
    def get_active_session(phone: str, match_text: str | None = None) -> dict | None:
        """
        Return an active question for a user.
        
        Args:
            phone: User's phone number
            match_text: Optional text from a quoted WhatsApp reply to disambiguate context.
            
        Returns:
            dict with keys {id, question, topic, sent_at} or None.
            If match_text is provided, tries to find the most relevant historical context.
            Otherwise, uses LIFO (DESC) to match the most recent thing the user read.
        """
        with get_conn() as conn:
            if match_text:
                # 1. Try to find content that matches the quoted text
                row = conn.execute(
                    """
                    SELECT id, question, topic, sent_at, follow_up_count
                    FROM sessions
                    WHERE phone_number = %s AND (question ILIKE %s OR topic ILIKE %s)
                    ORDER BY sent_at DESC
                    LIMIT 1
                    """,
                    (phone, f"%{match_text}%", f"%{match_text}%"),
                ).fetchone()
                if row:
                    logger.debug(f"[{phone}] Context match found via quote: '{row['topic']}'")
                    return dict(row)

            # 2. Fallback to LIFO (DESC) — match the most recent delivery
            row = conn.execute(
                """
                SELECT id, question, topic, sent_at, follow_up_count
                FROM sessions
                WHERE phone_number = %s AND awaiting_reply = 1
                ORDER BY sent_at DESC
                LIMIT 1
                """,
                (phone,),
            ).fetchone()
            
        if row:
            logger.debug(
                f"[{phone}] Active session found (LIFO) — topic='{row['topic']}' id={row['id']}"
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
    def prune_expired_sessions(phone: str, days: int = 7) -> None:
        """
        Mark sessions as inactive (awaiting_reply=0) if they are older than 'days'.
        This maintains a rolling window of interactive context for the user.
        """
        with get_conn() as conn:
            conn.execute(
                f"""
                UPDATE sessions 
                SET awaiting_reply = 0 
                WHERE phone_number = %s 
                  AND awaiting_reply = 1 
                  AND sent_at < NOW() - INTERVAL '{days} days'
                """,
                (phone,),
            )
        logger.info(f"[{phone}] Pruned sessions older than {days} days.")

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
