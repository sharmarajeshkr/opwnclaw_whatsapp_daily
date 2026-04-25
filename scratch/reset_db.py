import psycopg2
import psycopg2.extras
import sys
import os
sys.path.append(os.getcwd())

from app.core.config import settings
from app.database.db import init_db

# Step 1: Drop ALL tables in public schema
conn = psycopg2.connect(settings.get_database_url(), cursor_factory=psycopg2.extras.RealDictCursor)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
tables = [r['tablename'] for r in cur.fetchall()]
if tables:
    drop_sql = "DROP TABLE IF EXISTS " + ", ".join(tables) + " CASCADE"
    cur.execute(drop_sql)
    print(f"Dropped {len(tables)} tables:")
    for t in tables:
        print(f"  - {t}")
else:
    print("No tables found to drop.")
cur.close()
conn.close()

# Step 2: Recreate app schema (5 mandatory tables)
init_db()
print("\nSchema recreated successfully with 5 mandatory tables:")
print("  - user_configs")
print("  - user_status")
print("  - sessions")
print("  - performance_scores")
print("  - user_history")
