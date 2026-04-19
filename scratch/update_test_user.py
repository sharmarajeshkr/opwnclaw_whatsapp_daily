from src.core.db import get_conn
import datetime

phone = '919876543210'
past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=35)

with get_conn() as conn:
    conn.execute(
        "UPDATE user_configs SET created_at = %s, level = 'Beginner' WHERE phone_number = %s",
        (past, phone)
    )
print(f"Successfully updated {phone} created_at to {past}")
