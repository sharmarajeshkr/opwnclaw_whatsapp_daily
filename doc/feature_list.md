# Interview — Complete Feature List

## 1. Infrastructure & Architecture

| Feature | File | Detail |
|---|---|---|
| Multi-user isolation | `src/core/config.py` | Each user has independent config, session, history, and performance data |
| Pydantic-validated config | `src/core/config.py` | `UserConfig`, `TopicsConfig`, `ChannelsConfig` with typed fields |
| Per-user config persistence | `data/users/<phone>_config.json` | JSON backed, auto-created with defaults on first use |
| Environment config loader | `src/core/env.py` | `.env` based, validates LLM keys at startup |
| Structured logger | `src/core/logger.py` | Named loggers per module, writes to `data/bot.log` |
| Cross-platform process manager | `src/core/utils.py` | `psutil`-based start/stop bot processes on Windows + Linux |
| Multi-user orchestration daemon | `main.py` | Polls for paired users, spawns concurrent async tasks per user |
| Single-user mode | `main.py --phone` | Start bot for one specific user |
| Virtual env Python detection | `src/core/utils.py` | `_python_exe()` resolves `venv/Scripts/python.exe` or `venv/bin/python` |
| WAL-mode SQLite DB | `src/core/db.py` | `data/coach.db` with WAL journal for better concurrent reads |

---

## 2. WhatsApp Integration

| Feature | File | Detail |
|---|---|---|
| WhatsApp pairing via QR | `src/bot/client.py` | `neonize` library, QR saved as PNG to `data/qr_<phone>.png` |
| Auto-cleanup QR after pairing | `src/bot/client.py` | `ConnectedEv` handler deletes QR file after successful pair |
| One-shot pairing script | `src/core/utils.py` | `trigger_qr_script()` writes + launches `pair_<phone>.py` |
| Per-user SQLite session | `data/users/<phone>.sqlite3` | Neonize session persistence |
| Stale QR auto-cleanup | `src/core/utils.py` | `is_user_paired()` deletes stale QR if session exists |
| Send text message (with retry) | `src/bot/client.py` | 3 retries with exponential backoff |
| Send image with caption (retry) | `src/bot/client.py` | Same retry pattern for image delivery |
| Incoming message handler | `src/bot/client.py` | `register_incoming_handler()` wires callback via `MessageEv` |
| Connection timeout guard | `src/bot/client.py` | 300s `wait_for` timeout on connection, graceful error |

---

## 3. AI Coach Loop *(newly implemented)*

| Feature | File | Detail |
|---|---|---|
| **Active session tracking** | `src/core/session.py` | Stores which question was sent to which user in `sessions` DB table |
| **One active session per user** | `src/core/session.py` | `INSERT OR REPLACE` — new question overwrites old unanswered one |
| **Stale session auto-clear** | `src/core/session.py` | `clear_all_stale()` called at start of each daily cycle |
| **LLM answer evaluation** | `src/content/agent.py` | `evaluate_answer(question, user_reply, topic)` → score 0–10 + feedback + weak aspects |
| **Score clamping** | `src/content/agent.py` | Score always in `[0, 10]` regardless of LLM output |
| **Safe JSON parse with fallback** | `src/content/agent.py` | Strips markdown fences, regex extracts JSON, falls back gracefully |
| **Structured reply to user** | `src/scheduling/scheduler.py` | `🏆/✅/⚠️/❌ Score: X/10` with emoji verdict + feedback + review list |
| **Weak aspects highlighted** | `src/scheduling/scheduler.py` | `📌 Review: DLQ, idempotency` appended to feedback if aspects present |
| **Performance score storage** | `src/core/performance.py` | Every answer persisted to `performance_scores` table with timestamp |
| **Weak topic detection** | `src/core/performance.py` | `get_weak_topics()` — topics with avg < 6 in last 30 days, sorted weakest-first |
| **Weakness-aware scheduling** | `src/scheduling/scheduler.py` | Weak topics injected first before config topics in daily delivery |
| **Weekly performance report** | `src/scheduling/scheduler.py` | Every Sunday 09:00 — per-topic avg/min/max/attempts, weak topic callout |
| **[QUESTION]/[ANSWER] parsing** | `src/content/agent.py` | `_extract_block()` parses structured LLM response for session storage |
| **Legacy deep_dive wrapper** | `src/content/agent.py` | `get_deep_dive()` still works for backward compat |

---

## 4. Content Engine

| Feature | File | Detail |
|---|---|---|
| Architecture challenge (HLD/LLD) | `src/content/agent.py` | Generates Senior Architect–level system design challenge with deep solution |
| Deep-dive Q&A | `src/content/agent.py` | `get_deep_dive_with_question()` — returns scoreable question + full answer |
| Curated news/updates | `src/content/agent.py` | `get_curated_content()` — summarises research into WhatsApp-ready top-3 entries |
| History-based deduplication | `src/content/history.py` | Last 50 sent items per topic/category tracked in `data/history/<phone>.json` |
| Dual LLM backend | `src/content/llm.py` | Auto-selects OpenAI (gpt-4o-mini) or Gemini (gemini-pro) based on `.env` |
| DALL-E image stub | `src/content/llm.py` | Image generation scaffolded, disabled by default to avoid cost |

---

## 5. Scheduling

| Feature | File | Detail |
|---|---|---|
| Cron-based daily delivery | `src/scheduling/scheduler.py` | APScheduler cron job at user-configured `HH:MM` time |
| Weekly report cron | `src/scheduling/scheduler.py` | Every Sunday 09:00, independent of daily job |
| 5 configurable content slots | `src/scheduling/scheduler.py` | Topics 1–5: challenge, deep-dive ×2, fresh-updates ×2 |
| Adaptive topic priority | `src/scheduling/scheduler.py` | Weak topics from DB replace default topics in deep-dive slots |
| Config hot-reload | `src/scheduling/scheduler.py` | `refresh_config()` at start of each daily cycle |

---

## 6. Multi-Channel Delivery

| Feature | File | Detail |
|---|---|---|
| WhatsApp delivery | `src/bot/sender.py` | Primary channel, text + image |
| Telegram delivery | `src/bot/sender.py` | Bot token + chat ID, text + photo, auto-chunked at 4000 chars |
| Slack delivery | `src/bot/sender.py` | Webhook URL, text only |
| Parallel delivery | `src/bot/sender.py` | `asyncio.gather()` — all channels sent simultaneously |
| Title formatting | `src/bot/sender.py` | `*Title*\n\nBody` WhatsApp bold header prepended automatically |

---

## 7. Streamlit Dashboard (`app.py`)

| Feature | Detail |
|---|---|
| Glassmorphism dark UI | Inter font, gradient cards, blur background, hover animations |
| **Tab 1 — User Profiles** | Table + per-user card with status badge (Running / Ready / Scan QR) |
| Register new user | Phone input → triggers QR pairing script |
| QR display in-browser | PNG rendered inline for users pending pairing |
| QR refresh button | Per-user manual refresh |
| Per-user action buttons | ▶️ Start / ⏹️ Stop / 🗑️ Delete per user |
| **Tab 2 — Configure User** | Select user → edit schedule time, topics 1–5, Telegram + Slack credentials |
| Save config | Writes `UserConfig` to JSON |
| **Tab 3 — System Control** | Bulk Start All / Stop All buttons + status table |
| **Tab 4 — Logs** | Live tail last 100 lines of `data/bot.log` with refresh |
| Pairing gate | Tabs 2–4 only unlocked after at least one user is paired |

---

## 8. REST API (`api.py` + `src/api/routes.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/api/users` | GET | List all users with status |
| `/api/users/register` | POST | Register user + trigger QR |
| `/api/users/{phone}` | DELETE | Delete user + all data |
| `/api/users/{phone}/status` | GET | Pairing + running status |
| `/api/users/{phone}/config` | GET | Get user config |
| `/api/users/{phone}/config` | PUT | Partial-update user config |
| `/api/users/{phone}/start` | POST | Start bot for user |
| `/api/users/{phone}/stop` | POST | Stop bot for user |
| `/api/users/{phone}/qr` | POST | Re-trigger QR pairing |
| `/api/system/start-all` | POST | Start all bots daemon |
| `/api/system/stop-all` | POST | Stop all bots |
| `/api/system/logs` | GET | Tail log (1–1000 lines, default 100) |
| `/docs` | GET | Swagger UI auto-generated |
| `/redoc` | GET | ReDoc UI auto-generated |

---

## 9. Data Storage

| Store | Location | Contents |
|---|---|---|
| User configs | `data/users/<phone>_config.json` | Schedule, topics, channel credentials |
| WhatsApp sessions | `data/users/<phone>.sqlite3` | Neonize session (pairing state) |
| Send history | `data/history/<phone>.json` | Last 50 sent topics per category (dedup) |
| QR codes | `data/qr_<phone>.png` | Temporary, deleted after pairing |
| Bot log | `data/bot.log` | Rotating structured log |
| **Sessions** *(new)* | `data/coach.db → sessions` | Active question per user, awaiting_reply flag |
| **Performance scores** *(new)* | `data/coach.db → performance_scores` | Score/topic/date/weak_aspects per answer |

---

## 10. Test Suite (91 tests, 0 failures)

| File | Tests | Coverage Area |
|---|---|---|
| `tests/test_db.py` | 12 | Schema, WAL, commit/rollback, idempotency |
| `tests/test_session.py` | 14 | CRUD, overwrite, multi-user isolation, edge cases |
| `tests/test_performance.py` | 24 | Record, weak topics, lookback window, weekly/all-time summary |
| `tests/test_agent_eval.py` | 23 | JSON parse, clamping, fence stripping, fallback, block extraction |
| `tests/test_integration_coach_loop.py` | 13 | Full loop: session→score→weak→report + `handle_incoming` dispatch |
| `tests/conftest.py` | — | `sys.path` + logger suppression |

---

## Summary Count

| Category | Count |
|---|---|
| Infrastructure features | 10 |
| WhatsApp integration features | 9 |
| AI Coach Loop features *(new)* | 14 |
| Content engine features | 6 |
| Scheduling features | 5 |
| Multi-channel delivery features | 5 |
| Dashboard features | 13 |
| REST API endpoints | 15 |
| Data stores | 7 |
| **Total** | **84** |
