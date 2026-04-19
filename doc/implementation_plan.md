# AI Interview Coach — Full Feedback Loop Implementation (with DB)

## Overview

Right now Interview is a **one-way broadcaster**: it pushes content but never reads replies, never scores answers, and never adapts. This plan adds the complete **Question → Reply → Score → Memory → Adapt → Weekly Trend** loop without breaking any existing functionality.

### Storage Decision: SQLite (Built-in, Zero New Dependencies)

| Data | Current | Upgraded To |
|---|---|---|
| WhatsApp session | `data/users/<phone>.sqlite3` (neonize) | ✅ Keep as-is |
| Topic send history | `data/history/<phone>.json` | ✅ Keep as-is (not performance data) |
| User config | `data/users/<phone>_config.json` | ✅ Keep as-is |
| **Session state** (active Q) | ❌ Nothing | ✅ **`data/coach.db` — SQLite** |
| **Performance scores** | ❌ Nothing | ✅ **`data/coach.db` — SQLite** |

**Why SQLite over JSON files:**
- Already in use (neonize uses it) — zero new dependencies
- SQL `GROUP BY`, `AVG()`, `WHERE date > ...` are native → weekly aggregations in 1 line
- Concurrent-safe across multiple users (vs file locking issues with JSON)
- Easy to inspect with any SQLite viewer (DB Browser, DBeaver)
- Python `sqlite3` is stdlib — no pip install needed

---

## User Review Required

> [!IMPORTANT]
> The `register_incoming_handler()` in `scheduler.py` currently passes **no handler**, meaning all user replies are silently dropped. Wiring the new handler is the foundational change everything else depends on.

> [!WARNING]
> The bot currently **pushes to a target number** (not necessarily the same number paired). Incoming messages come from the **paired number**. If a user receives content on a different WhatsApp number/group, reply routing needs to be confirmed before wiring the handler.

> [!NOTE]
> Scoring uses one LLM call per user reply. Estimate: ~$0.001–0.005 per evaluation on GPT-4o-mini.

---

## Database Schema

**File:** `data/coach.db` (single shared SQLite DB for all users)

### Table 1: `sessions`
Tracks the active question waiting for a user reply.

```sql
CREATE TABLE IF NOT EXISTS sessions (
    phone_number    TEXT PRIMARY KEY,
    question        TEXT NOT NULL,        -- exact question text sent to user
    topic           TEXT NOT NULL,        -- e.g. "Kafka", "Circuit Breaker"
    sent_at         TEXT NOT NULL,        -- ISO datetime string
    awaiting_reply  INTEGER DEFAULT 1     -- 1 = waiting, 0 = done
);
```

**Lifecycle:**
- `INSERT/REPLACE` when bot sends a question
- `UPDATE SET awaiting_reply=0` after scoring
- Auto-cleared every 24h by `daily_task()` (stale sessions reset)

---

### Table 2: `performance_scores`
Stores every scored answer for every user over time.

```sql
CREATE TABLE IF NOT EXISTS performance_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number    TEXT NOT NULL,
    topic           TEXT NOT NULL,        -- e.g. "Kafka"
    score           INTEGER NOT NULL,     -- 0–10
    weak_aspects    TEXT,                 -- JSON array: ["DLQ", "idempotency"]
    feedback        TEXT,                 -- LLM feedback text
    answered_at     TEXT NOT NULL         -- ISO datetime string
);

CREATE INDEX IF NOT EXISTS idx_perf_phone_topic
    ON performance_scores(phone_number, topic);

CREATE INDEX IF NOT EXISTS idx_perf_answered_at
    ON performance_scores(answered_at);
```

**Key Queries Used:**
```sql
-- Weak topics (avg score < 6, last 30 days)
SELECT topic, AVG(score) as avg_score
FROM performance_scores
WHERE phone_number = ? AND answered_at >= date('now', '-30 days')
GROUP BY topic
HAVING avg_score < 6
ORDER BY avg_score ASC;

-- Weekly summary
SELECT topic, AVG(score) as avg_score, COUNT(*) as attempts
FROM performance_scores
WHERE phone_number = ? AND answered_at >= date('now', '-7 days')
GROUP BY topic
ORDER BY avg_score ASC;

-- All-time stats per topic
SELECT topic, AVG(score), MIN(score), MAX(score), COUNT(*)
FROM performance_scores
WHERE phone_number = ?
GROUP BY topic;
```

---

## Data Flow (The New Loop)

```
[Scheduler] → sends Question to user
      ↓ INSERT into sessions table
[User] → replies on WhatsApp
      ↓
[on_message handler] → SELECT from sessions WHERE phone=? AND awaiting_reply=1
      ↓
[Evaluator.score()] → LLM evaluates: score 0–10 + feedback + weak_aspects
      ↓
[PerformanceTracker.record()] → INSERT into performance_scores
      ↓ UPDATE sessions SET awaiting_reply=0
[reply to user] → "Score: 7/10 — Good! Missed: Circuit Breaker fallback"
      ↓
[Scheduler next run] → SELECT weak topics → prioritize in daily_task
      ↓
[Every Sunday 09:00] → SELECT weekly summary → send WhatsApp report
```

---

## Proposed Changes

### Phase 0 — Database Layer (Foundation)

#### [NEW] `src/core/db.py`

Central DB module. All other modules import from here — nothing touches `coach.db` directly.

```python
import sqlite3
import os
from contextlib import contextmanager
from src.core.logger import get_logger

DB_PATH = os.path.join("data", "coach.db")
logger = get_logger("CoachDB")

def init_db():
    """Create tables if they don't exist. Called once at startup."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                phone_number    TEXT PRIMARY KEY,
                question        TEXT NOT NULL,
                topic           TEXT NOT NULL,
                sent_at         TEXT NOT NULL,
                awaiting_reply  INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS performance_scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number    TEXT NOT NULL,
                topic           TEXT NOT NULL,
                score           INTEGER NOT NULL,
                weak_aspects    TEXT,
                feedback        TEXT,
                answered_at     TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_perf_phone_topic
                ON performance_scores(phone_number, topic);

            CREATE INDEX IF NOT EXISTS idx_perf_answered_at
                ON performance_scores(answered_at);
        """)

@contextmanager
def get_conn():
    """Thread-safe SQLite connection context manager."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

`init_db()` is called once in `main.py` at startup — no migration scripts needed.

---

### Phase 1 — Session Manager

#### [NEW] `src/core/session.py`

```python
import json
from datetime import datetime, timezone
from src.core.db import get_conn

class SessionManager:

    @staticmethod
    def set_active_question(phone: str, question: str, topic: str):
        """Called right after bot sends a question."""
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                    (phone_number, question, topic, sent_at, awaiting_reply)
                VALUES (?, ?, ?, ?, 1)
            """, (phone, question, topic, datetime.now(timezone.utc).isoformat()))

    @staticmethod
    def get_active_session(phone: str) -> dict | None:
        """Returns {question, topic, sent_at} or None if no active session."""
        with get_conn() as conn:
            row = conn.execute("""
                SELECT question, topic, sent_at
                FROM sessions
                WHERE phone_number = ? AND awaiting_reply = 1
            """, (phone,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def clear_session(phone: str):
        """Mark session as done after scoring."""
        with get_conn() as conn:
            conn.execute("""
                UPDATE sessions SET awaiting_reply = 0
                WHERE phone_number = ?
            """, (phone,))
```

---

### Phase 2 — Answer Evaluator

#### [MODIFY] `src/content/agent.py`

Add `evaluate_answer()` method:

```python
async def evaluate_answer(self, question: str, user_answer: str, topic: str) -> dict:
    """
    Returns:
      {"score": 7, "feedback": "...", "weak_aspects": ["DLQ", "idempotency"]}
    """
    prompt = f"""
    You are an expert senior engineering interviewer assessing a candidate's answer.

    TOPIC: {topic}

    QUESTION ASKED:
    {question}

    CANDIDATE'S ANSWER:
    {user_answer}

    Evaluate and return ONLY valid JSON (no extra text):
    {{
      "score": <integer 0-10>,
      "feedback": "<2-3 lines of WhatsApp-ready feedback>",
      "weak_aspects": ["<concept they missed>", ...]
    }}

    Scoring guide:
    - 9-10: Exceptional, covers all key aspects
    - 7-8: Good, minor gaps
    - 5-6: Partial, important concepts missing
    - 3-4: Weak, fundamental misunderstanding
    - 0-2: Off-topic or no real answer
    """
    raw = await self.llm.generate_response(prompt)
    try:
        import json, re
        json_str = re.search(r'\{.*\}', raw, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return {"score": 5, "feedback": "Answer received! Keep practicing.", "weak_aspects": []}
```

Also refactor `get_deep_dive()` → `get_deep_dive_with_question()` returning `(question_text, full_content)`:

```python
async def get_deep_dive_with_question(self, subject: str) -> tuple[str, str]:
    """Returns (scoreable_question, full_WhatsApp_message)"""
    # Prompt asks LLM to separate the QUESTION block from ANSWER block
    # Returns both so scheduler can store question in session, send full message to user
```

---

### Phase 3 — Performance Tracker

#### [NEW] `src/core/performance.py`

```python
import json
from datetime import datetime, timezone
from src.core.db import get_conn

class PerformanceTracker:

    @staticmethod
    def record_score(phone: str, topic: str, score: int, weak_aspects: list, feedback: str):
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO performance_scores
                    (phone_number, topic, score, weak_aspects, feedback, answered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (phone, topic, score, json.dumps(weak_aspects), feedback,
                  datetime.now(timezone.utc).isoformat()))

    @staticmethod
    def get_weak_topics(phone: str, threshold: int = 6) -> list[str]:
        """Returns topics with avg score below threshold, weakest first."""
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT topic, AVG(score) as avg_score
                FROM performance_scores
                WHERE phone_number = ? AND answered_at >= date('now', '-30 days')
                GROUP BY topic
                HAVING avg_score < ?
                ORDER BY avg_score ASC
            """, (phone, threshold)).fetchall()
        return [row["topic"] for row in rows]

    @staticmethod
    def get_weekly_summary(phone: str) -> list[dict]:
        """Returns per-topic stats for the last 7 days."""
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT
                    topic,
                    ROUND(AVG(score), 1) as avg_score,
                    COUNT(*) as attempts,
                    MIN(score) as min_score,
                    MAX(score) as max_score
                FROM performance_scores
                WHERE phone_number = ?
                  AND answered_at >= date('now', '-7 days')
                GROUP BY topic
                ORDER BY avg_score ASC
            """, (phone,)).fetchall()
        return [dict(row) for row in rows]
```

---

### Phase 4 — Incoming Message Handler

#### [MODIFY] `src/scheduling/scheduler.py`

Replace the broken `register_incoming_handler()` call and add a real handler:

```python
from src.core.session import SessionManager
from src.core.performance import PerformanceTracker

async def handle_incoming(self, client, message_ev):
    """Called on every incoming WhatsApp message."""
    # Extract sender phone from JID (e.g. "919789824976@s.whatsapp.net")
    sender_jid = str(message_ev.Info.MessageSource.Sender)
    phone = sender_jid.split("@")[0]

    text = message_ev.Message.Conversation or \
           message_ev.Message.ExtendedTextMessage.Text or ""
    text = text.strip()

    if not text:
        return  # Ignore media/sticker messages

    session = SessionManager.get_active_session(phone)
    if not session:
        return  # No active question — silently ignore

    # Score the answer
    result = await self.agent.evaluate_answer(
        question=session["question"],
        user_answer=text,
        topic=session["topic"]
    )

    # Persist to DB
    PerformanceTracker.record_score(
        phone, session["topic"],
        result["score"], result["weak_aspects"], result["feedback"]
    )
    SessionManager.clear_session(phone)

    # Reply with score + feedback
    emoji = "🏆" if result["score"] >= 8 else "✅" if result["score"] >= 6 else "⚠️"
    msg = f"{emoji} *Score: {result['score']}/10*\n\n{result['feedback']}"
    if result["weak_aspects"]:
        msg += f"\n\n📌 *Review:* {', '.join(result['weak_aspects'])}"
    await self.whatsapp.send_message(msg)

async def start(self):
    await self.whatsapp.connect()
    # FIXED: pass real handler
    self.whatsapp.register_incoming_handler(
        handler=lambda c, m: asyncio.create_task(self.handle_incoming(c, m))
    )
    ...
```

---

### Phase 5 — Weakness-Aware Scheduling

#### [MODIFY] `src/scheduling/scheduler.py` — `daily_task()`

```python
async def daily_task(self):
    # Get config topics
    config = self.sender.config.topics
    config_topics = [t for t in [config.topic_2, config.topic_3] if t]

    # Get weak topics from DB (last 30 days, score < 6)
    weak_topics = PerformanceTracker.get_weak_topics(self.phone_number)

    # Priority: weak first, then config, deduplicated, cap at 2
    merged = weak_topics + [t for t in config_topics if t not in weak_topics]
    selected_topics = merged[:2]

    for topic in selected_topics:
        question, full_content = await self.agent.get_deep_dive_with_question(topic)

        # Store question in session DB (so reply can be scored)
        SessionManager.set_active_question(self.phone_number, question, topic)

        await self.sender.send_to_all(full_content, title=f"Deep Dive: {topic}")
        await asyncio.sleep(5)
```

---

### Phase 6 — Weekly Report

#### [MODIFY] `src/scheduling/scheduler.py`

```python
# Add to start():
self.scheduler.add_job(
    self.weekly_report_task,
    trigger="cron",
    day_of_week="sun",
    hour=9,
    minute=0
)

async def weekly_report_task(self):
    summary = PerformanceTracker.get_weekly_summary(self.phone_number)

    if not summary:
        await self.whatsapp.send_message("📊 No answers recorded this week. Reply to daily questions to track your progress!")
        return

    lines = ["📊 *Weekly Performance Report*", "─────────────────────"]
    for row in summary:
        avg = row["avg_score"]
        icon = "🏆" if avg >= 8 else "✅" if avg >= 6 else "⚠️"
        lines.append(f"{icon} *{row['topic']}*  →  Avg: {avg}/10  ({row['attempts']} attempts)")

    weak = [r["topic"] for r in summary if r["avg_score"] < 6]
    lines.append("─────────────────────")
    lines.append(f"📝 Total this week: {sum(r['attempts'] for r in summary)} questions answered")
    if weak:
        lines.append(f"🔥 *Drill more:* {', '.join(weak)}")

    await self.whatsapp.send_message("\n".join(lines))
```

---

#### [MODIFY] `main.py`
Call `init_db()` once at startup before the scheduler starts:

```python
from src.core.db import init_db

if __name__ == "__main__":
    init_db()   # ← Creates coach.db + tables if not exists
    # ... rest of startup
```

---

## Complete File Change Summary

| File | Action | What Changes |
|---|---|---|
| `src/core/db.py` | **NEW** | SQLite connection manager + `init_db()` |
| `src/core/session.py` | **NEW** | Session CRUD using `sessions` table |
| `src/core/performance.py` | **NEW** | Score storage + weak topic queries + weekly summary |
| `src/content/agent.py` | **MODIFY** | Add `evaluate_answer()`, refactor `get_deep_dive()` |
| `src/scheduling/scheduler.py` | **MODIFY** | Wire handler, weak-topic priority, weekly cron job |
| `main.py` | **MODIFY** | Call `init_db()` at startup |
| `requirements.txt` | **NO CHANGE** | `sqlite3` is Python stdlib ✅ |

---

## Implementation Order

```
Phase 0 → db.py (init_db, get_conn)          ~10 min
Phase 1 → session.py                          ~10 min
Phase 2 → agent.evaluate_answer()             ~20 min
Phase 3 → performance.py                      ~15 min
Phase 4 → handler wiring in scheduler.py      ~15 min
Phase 5 → weak-topic scheduling               ~10 min
Phase 6 → weekly_report_task()                ~10 min
──────────────────────────────────────────────
Total:                                        ~90 min
```

---

## Verification Plan

### Startup Check
```bash
python -c "from src.core.db import init_db; init_db(); print('DB OK')"
```

### Inspect DB After First Run
```bash
# Using sqlite3 CLI
sqlite3 data/coach.db ".tables"
sqlite3 data/coach.db "SELECT * FROM sessions;"
sqlite3 data/coach.db "SELECT * FROM performance_scores;"
```

### Simulate Full Loop (Manual Test)
1. Start bot → verify question sent to WhatsApp
2. Reply with weak answer → score 3–5 should come back with feedback
3. Reply with strong answer → score 7–9 should come back
4. Check DB: `SELECT topic, avg(score) FROM performance_scores GROUP BY topic;`
5. Trigger `weekly_report_task()` manually → WhatsApp summary arrives
6. Wait for next `daily_task()` → confirm weak topic appears **first** in delivery

### Edge Cases
- User replies when no active session → silently ignored (session lookup returns None)
- LLM returns malformed JSON from evaluator → fallback score 5 with generic message
- User never replies → session auto-cleared at next `daily_task()` startup
