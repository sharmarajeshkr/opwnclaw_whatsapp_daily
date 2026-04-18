from src.core.db import get_conn

class UserHistoryManager:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number

    def add_to_history(self, category: str, item: str):
        """Adds an item to the user's history in PostgreSQL to avoid repetition."""
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_history (phone_number, category, item)
                VALUES (%s, %s, %s)
                ON CONFLICT (phone_number, category, item) DO NOTHING
                """,
                (self.phone_number, category, item)
            )
            
            # Pruning strategy: keep only last 50 entries per category per user
            # This is slightly more complex in SQL but manageable
            conn.execute(
                """
                DELETE FROM user_history 
                WHERE (phone_number, category, item) IN (
                    SELECT phone_number, category, item 
                    FROM (
                        SELECT phone_number, category, item, 
                               ROW_NUMBER() OVER (PARTITION BY phone_number, category ORDER BY created_at DESC) as rn
                        FROM user_history
                        WHERE phone_number = %s AND category = %s
                    ) tmp 
                    WHERE rn > 50
                )
                """,
                (self.phone_number, category)
            )

    def get_history(self, category: str):
        """Returns the list of historical items for a specific category from PostgreSQL."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT item FROM user_history WHERE phone_number = %s AND category = %s ORDER BY created_at DESC",
                (self.phone_number, category)
            ).fetchall()
        return [row["item"] for row in rows]
