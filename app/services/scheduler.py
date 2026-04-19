import os
import asyncio
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.agents.interview_agent import InterviewAgent
from app.agents.scoring_agent import ScoringAgent
from app.agents.deep_dive_agent import DeepDiveAgent
from app.agents.news_agent import NewsAgent
from app.channels.whatsapp.client import WhatsAppClient
from app.channels.whatsapp.handler import ChannelSender
from app.core.config import ConfigManager
from app.services.session_manager import SessionManager
from app.services.performance_tracker import PerformanceTracker
from app.core.logging import get_logger, log_duration
from app.core.utils import ContextAdapter
from app.core.limiter import MultiUserLimiter
from app.mcp.client import run_medium_query

logger = get_logger("InterviewScheduler")

# Per-User Limiter: 5 RPM (0.083 tokens/sec) with burst capacity of 2
user_antispam = MultiUserLimiter(rate=0.083, capacity=2)


class InterviewScheduler:
    def __init__(self, whatsapp: WhatsAppClient, phone_number: str):
        self.whatsapp = whatsapp
        self.phone_number = phone_number
        
        # Initialize specialized agents
        self.interview_agent = InterviewAgent(phone_number)
        self.scoring_agent = ScoringAgent(phone_number)
        self.deep_dive_agent = DeepDiveAgent(phone_number)
        self.news_agent = NewsAgent(phone_number)
        self.logger = ContextAdapter(logger, {"phone": phone_number})
        self.sender = ChannelSender(whatsapp, phone_number)
        self.scheduler = AsyncIOScheduler()
        self.config = ConfigManager.load_config(phone_number)
        self.schedule_time = self.config.schedule_time
        self.level = self.config.level
        self.skill_profile = self.config.skill_profile
        self.created_at = self.config.created_at

    # ------------------------------------------------------------------
    # Phase 5 — Weakness-Aware Daily Task
    # ------------------------------------------------------------------

    def _get_progression_context(self):
        """Calculate week number based on created_at date."""
        now = datetime.datetime.now(datetime.timezone.utc)
        start_date = self.created_at
        
        # Ensure start_date is timezone-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            
        delta = now - start_date
        week_num = (delta.days // 7) + 1
        
        # ── Auto-Progression Logic ─────────────────────────────────────
        # Week 1-2: Beginner, Week 3-4: Intermediate, Week 5+: Advanced
        order = ["Beginner", "Intermediate", "Advanced"]
        target_level_idx = 0
        if week_num >= 5:
            target_level_idx = 2
        elif week_num >= 3:
            target_level_idx = 1
            
        current_level_idx = order.index(self.level) if self.level in order else 0
        
        if target_level_idx > current_level_idx:
            new_level = order[target_level_idx]
            self.logger.info(f"🚀 [{self.phone_number}] Auto-promoting from {self.level} to {new_level} (Week {week_num})")
            
            # Update DB
            self.config.level = new_level
            ConfigManager.save_config(self.phone_number, self.config)
            self.level = new_level
            
            # Notify user via WhatsApp (async)
            promo_msg = (
                f"🎊 *Congratulations!* 🎊\n\n"
                f"You've been automatically promoted to the *{new_level}* level based on your {week_num} weeks of consistent practice! 🚀\n\n"
                f"Your daily challenges and deep-dives will now feature increased complexity. Keep pushing! 💪"
            )
            asyncio.create_task(self.whatsapp.send_message(promo_msg))
            
        return self.level, week_num

    async def daily_task(self):
        self.logger.info(f"🚀 [{self.phone_number}] Starting content delivery cycle")

        # Clear any stale unanswered session from yesterday so scoring
        # doesn't accidentally apply to the wrong question.
        SessionManager.clear_all_stale(self.phone_number)

        self.sender.refresh_config()
        config = self.sender.config
        topics = config.topics

        # 1. Architecture Challenge
        level, week = self._get_progression_context()
        self.logger.info(f"[{self.phone_number}] Progression: level={level}, week={week}")

        if topics.topic_1:
            detailed_text, image_prompt = await self.interview_agent.get_daily_challenge(
                level=level, week=week, skill_profile=self.skill_profile
            )
            image_path = await self.interview_agent.llm.generate_image(image_prompt)
            await self.sender.send_to_all(
                detailed_text, image_path,
                "Visual Diagram for the Challenge",
                title=topics.topic_1
            )
            await asyncio.sleep(5)

        # 2 & 3. Deep-Dive topics — weakness-aware ordering
        #
        # Strategy:
        #   • Pull topics where user's avg score < 6 (last 30 days), weakest first.
        #   • Append config topics so we always have fallback content.
        #   • Deduplicate, take top 2.
        config_deep_topics = [t for t in [topics.topic_2, topics.topic_3] if t]
        weak_topics = PerformanceTracker.get_weak_topics(self.phone_number)

        merged = weak_topics + [t for t in config_deep_topics if t not in weak_topics]
        selected_topics = merged[:2]

        if not selected_topics:
            selected_topics = config_deep_topics  # safety fallback

        if weak_topics:
            self.logger.info(
                f"[{self.phone_number}] Weak topics prioritised: {weak_topics} "
                f"→ selected: {selected_topics}"
            )

        for topic in selected_topics:
            # get_deep_dive_with_question returns (question_text, full_message)
            # We store the question in SessionManager for later scoring.
            question, full_content = await self.deep_dive_agent.get_deep_dive_with_question(
                topic, level=level, week=week, skill_profile=self.skill_profile
            )
            SessionManager.set_active_question(self.phone_number, question, topic)

            await self.sender.send_to_all(full_content, title=f"Deep Dive: {topic}")
            await asyncio.sleep(5)

        # 4. Fresh Updates 1
        if topics.topic_4:
            content = await self.news_agent.get_curated_content(
                "Tech_news", f"Top global news about {topics.topic_4} for today."
            )
            await self.sender.send_to_all(content, title=f"Fresh Updates: {topics.topic_4}")
            await asyncio.sleep(5)

        # 5. Fresh Updates 2 (MCP Integration via Medium)
        if topics.topic_5:
            try:
                # Convert topic string to Medium URL tag format (e.g. 'Artificial Intelligence' -> 'artificial-intelligence')
                tag = topics.topic_5.lower().replace(' ', '-')
                mcp_data = await run_medium_query(tag, is_user=False, limit=3)
                
                # Have the LLM rewrite the raw MCP output into an engaging WhatsApp digest
                prompt = (
                    f"I just pulled the live Medium.com RSS feed for '{topics.topic_5}'. "
                    f"Here is the raw data from my MCP tools:\n\n{mcp_data}\n\n"
                    "Please rewrite this into a friendly, structured WhatsApp reading list. "
                    "Include the exact links so the user can read them. Do not hallucinate any posts."
                )
                
                content = await self.news_agent.get_curated_content("Medium_updates", prompt)
                await self.sender.send_to_all(content, title=f"Latest from Medium: {topics.topic_5}")
            except Exception as e:
                self.logger.error(f"MCP Integration Error for {topics.topic_5}: {e}")
                # Fallback to pure LLM if MCP server crashes
                content = await self.news_agent.get_curated_content(
                    "Global_news", f"Top global news about {topics.topic_5} for today."
                )
                await self.sender.send_to_all(content, title=f"Fresh Updates: {topics.topic_5}")

        self.logger.info(f"✅ [{self.phone_number}] Content delivery cycle completed.")

    # ------------------------------------------------------------------
    # Phase 4 — Incoming Message Handler (Reply → Score → Feedback)
    # ------------------------------------------------------------------

    async def handle_incoming(self, client, message_ev):
        """
        Called on every incoming WhatsApp message.

        Flow:
          1. Extract sender phone + message text
          2. Look up active session in DB
          3. Score the answer with LLM
          4. Persist score to performance_scores table
          5. Clear session
          6. Send feedback to user
        """
        try:
            # ── Verify Message Source and Target Chat ──────────────────
            is_from_me = getattr(message_ev.Info.MessageSource, "IsFromMe", False)
            chat_jid = getattr(message_ev.Info.MessageSource, "Chat", None)
            chat_id = getattr(chat_jid, "User", "").strip() if chat_jid else ""
            
            sender_jid = getattr(message_ev.Info.MessageSource, "Sender", None)
            sender_id = getattr(sender_jid, "User", "").strip() if sender_jid else ""
            
            target = self.config.channels.whatsapp_target
            
            # The message is a reply to the bot from the target user
            # We want to process messages that are either:
            # 1. Sent from the target phone TO the bot (sender_id == target)
            # 2. Sent by the bot TO the target phone (for self-chat testing, is_from_me=True and chat_id == target)
            if sender_id != target and not (is_from_me and chat_id == target):
                # Also allow pure self-chat (talking to "You")
                if not (is_from_me and chat_id == sender_id):
                    return

            # Since the daemon is tied to exactly one user session, we reliably use its own number
            phone = self.phone_number

            # ── Extract plain text ─────────────────────────────────────
            msg = message_ev.Message
            text = (
                getattr(msg, "conversation", "")
                or getattr(getattr(msg, "extendedTextMessage", None), "text", "")
                or ""
            ).strip()

            if not text:
                return  # Ignore media, stickers, reactions

            # ── Per-User Rate Limit Check ──────────────────────────────
            if not await user_antispam.consume(phone, wait=False):
                self.logger.warning(f"⚠️ [{phone}] Rate limit exceeded. Ignoring reply.")
                # We don't send a message back to avoid a feedback loop with spammers
                return

            self.logger.info(f"📩 [{phone}] Incoming reply: {text}")

            # ── Look up active session ─────────────────────────────────
            session = SessionManager.get_active_session(phone)
            if not session:
                self.logger.debug(f"[{phone}] No active session — ignoring reply.")
                
                # Send a gentle fallback message so the user knows the bot is alive
                fallback_msg = (
                    "🤖 *Interview Coach*\n\n"
                    "I don't have an active question pending for you right now!\n"
                    "Wait for your next daily delivery to answer and get scored. 🚀"
                )
                await self.whatsapp.send_message(fallback_msg)
                return

            # ── Evaluate with LLM ──────────────────────────────────────
            self.logger.info(f"[{phone}] Evaluating answer for topic='{session['topic']}'...")
            level, week = self._get_progression_context()
            
            # Allow follow-up if we haven't done one yet for this session
            allow_follow_up = session.get("follow_up_count", 0) < 1
            
            result = await self.scoring_agent.evaluate_answer(
                question=session["question"],
                user_answer=text,
                topic=session["topic"],
                level=level
            )

            # ── Check for Follow-Up Question ───────────────────────────
            follow_up = result.get("follow_up_question")
            if allow_follow_up and follow_up and follow_up.strip().lower() != "null":
                self.logger.info(f"[{phone}] Sending follow-up for topic='{session['topic']}'")
                
                # Update session instead of clearing it
                SessionManager.update_session_with_follow_up(session["id"], follow_up.strip())
                
                # Send follow-up to user
                await self.whatsapp.send_message(f"🤔 *Follow-up Question:*\n\n{follow_up.strip()}")
                return

            # ── If no follow-up, proceed to final scoring ──────────────
            PerformanceTracker.record_score(
                phone=phone,
                topic=session["topic"],
                score=result["score"],
                weak_aspects=result["weak_aspects"],
                feedback=result["feedback"],
            )

            # ── Update Streak ─────────────────────────────────────────
            new_streak = PerformanceTracker.update_streak(phone)
            SessionManager.clear_session(session["id"])

            # ── Send feedback back to user ─────────────────────────────
            score = result["score"]
            if score >= 8:
                emoji = "🏆"
                verdict = "Excellent!"
            elif score >= 6:
                emoji = "✅"
                verdict = "Good answer!"
            elif score >= 4:
                emoji = "⚠️"
                verdict = "Needs improvement."
            else:
                emoji = "❌"
                verdict = "Keep practising!"

            streak_line = f"\n\n🔥 *{new_streak} Day Streak!* Keep it up." if new_streak > 1 else ""

            feedback_msg = (
                f"{emoji} *Score: {score}/10 — {verdict}*\n\n"
                f"{result['feedback']}"
                f"{streak_line}"
            )
            if result["weak_aspects"]:
                aspects = ", ".join(result["weak_aspects"])
                feedback_msg += f"\n\n📌 *Review these concepts:* {aspects}"

            await self.whatsapp.send_message(feedback_msg)
            self.logger.info(f"✅ [{phone}] Feedback sent — score {score}/10, streak {new_streak}")

        except Exception as exc:
            self.logger.error(f"handle_incoming error: {exc}", exc_info=True)

    # ------------------------------------------------------------------
    # Phase 6 — Weekly Report (Every Sunday 09:00)
    # ------------------------------------------------------------------

    async def weekly_report_task(self):
        """
        Calculates and sends a comprehensive weekly performance summary.
        Includes Score (0-100), Strengths, and Weaknesses.
        """
        self.logger.info(f"📊 [{self.phone_number}] Generating enhanced weekly report...")
        summary = PerformanceTracker.get_weekly_summary(self.phone_number)

        if not summary:
            msg = (
                "📊 *Weekly Report*\n\n"
                "No answers recorded this week.\n"
                "Reply to the daily questions to track your progress! 💬"
            )
            await self.whatsapp.send_message(msg)
            return

        # Calculate Overall Learning Score
        avg_scores = [float(s["avg_score"]) for s in summary]
        weekly_score = int((sum(avg_scores) / len(avg_scores)) * 10) if avg_scores else 0
        
        strengths = [s["topic"] for s in summary if float(s["avg_score"]) >= 8.0]
        weaknesses = [s["topic"] for s in summary if float(s["avg_score"]) < 6.0]

        lines = [
            "📊 *Weekly Performance Report*",
            f"Overall Learning Score: *{weekly_score}/100*",
            "─────────────────────────"
        ]

        if strengths:
            lines.append(f"✅ *Strengths:* {', '.join(strengths)}")
        
        if weaknesses:
            lines.append(f"⚠️ *Focus Areas:* {', '.join(weaknesses)}")
            
        lines.append("\n*Detailed Breakdown:*")

        for row in summary:
            mastery = ""
            if self.level == "Advanced" and row["avg_score"] >= 9.0:
                 mastery = " 💎 *Advanced Mastery*"
                 
            lines.append(
                f"🔹 *{row['topic']}*{mastery}\n"
                f"   Avg: {row['avg_score']}/10  |  Best: {row['max_score']}"
            )

        total_attempts = sum(r["attempts"] for r in summary)
        lines.append("─────────────────────────")
        lines.append(f"📝 *Total answered this week:* {total_attempts} questions")

        await self.whatsapp.send_message("\n".join(lines))
        self.logger.info(f"✅ [{self.phone_number}] Enhanced weekly report sent.")

    # ------------------------------------------------------------------
    # Per-Topic Delivery Tasks
    # ------------------------------------------------------------------

    def _make_topic_task(self, slot: int):
        """Return an async function that delivers only the content for a given topic slot (1-5)."""
        async def _task():
            self.sender.refresh_config()
            config = self.sender.config
            topics = config.topics
            topic_name = getattr(topics, f"topic_{slot}", "")
            if not topic_name:
                return

            self.logger.info(f"[{self.phone_number}] Delivering topic {slot}: {topic_name}")
            SessionManager.clear_all_stale(self.phone_number)
            level, week = self._get_progression_context()

            if slot == 1:
                detailed_text, image_prompt = await self.interview_agent.get_daily_challenge(
                    level=level, week=week, skill_profile=self.skill_profile
                )
                image_path = await self.interview_agent.llm.generate_image(image_prompt)
                await self.sender.send_to_all(
                    detailed_text, image_path,
                    "Visual Diagram for the Challenge",
                    title=topic_name
                )
            elif slot in (2, 3):
                weak_topics = PerformanceTracker.get_weak_topics(self.phone_number)
                topic = weak_topics[0] if weak_topics else topic_name
                question, full_content = await self.deep_dive_agent.get_deep_dive_with_question(
                    topic, level=level, week=week, skill_profile=self.skill_profile
                )
                SessionManager.set_active_question(self.phone_number, question, topic)
                await self.sender.send_to_all(full_content, title=f"Deep Dive: {topic}")
            elif slot == 4:
                content = await self.agent.get_curated_content(
                    "Tech_news", f"Top global news about {topic_name} for today."
                )
                await self.sender.send_to_all(content, title=f"Fresh Updates: {topic_name}")
            elif slot == 5:
                try:
                    tag = topic_name.lower().replace(" ", "-")
                    mcp_data = await run_medium_query(tag, is_user=False, limit=3)
                    prompt = (
                        f"I just pulled the live Medium.com RSS feed for '{topic_name}'. "
                        f"Here is the raw data from my MCP tools:\n\n{mcp_data}\n\n"
                        "Please rewrite this into a friendly, structured WhatsApp reading list. "
                        "Include the exact links so the user can read them. Do not hallucinate any posts."
                    )
                    content = await self.news_agent.get_curated_content("Medium_updates", prompt)
                    await self.sender.send_to_all(content, title=f"Latest from Medium: {topic_name}")
                except Exception as e:
                    self.logger.error(f"MCP Error for {topic_name}: {e}")
                    content = await self.news_agent.get_curated_content(
                        "Global_news", f"Top global news about {topic_name} for today."
                    )
                    await self.sender.send_to_all(content, title=f"Fresh Updates: {topic_name}")

            self.logger.info(f"✅ [{self.phone_number}] Topic {slot} delivery done.")

        _task.__name__ = f"topic_{slot}_task"
        return _task

    def _resolve_time(self, topic_time: str, global_time: str) -> tuple[int, int]:
        """Return (hour, minute) from topic_time if valid, else fall back to global_time."""
        raw = (topic_time or "").strip()
        if raw and ":" in raw:
            try:
                h, m = map(int, raw.split(":"))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    return h, m
            except ValueError:
                pass
        h, m = map(int, global_time.split(":"))
        return h, m

    def _register_topic_jobs(self, config, timezone_str: str):
        """Register one APScheduler cron job per topic, each at its own time."""
        self._topic_jobs = []
        for slot in range(1, 6):
            topic_name = getattr(config.topics, f"topic_{slot}", "")
            if not topic_name:
                continue
            topic_time = getattr(config.topics, f"topic_{slot}_time", "")
            hour, minute = self._resolve_time(topic_time, config.schedule_time)
            job = self.scheduler.add_job(
                self._make_topic_task(slot),
                trigger="cron",
                hour=hour,
                minute=minute,
                timezone=timezone_str,
                id=f"{self.phone_number}_topic_{slot}",
                replace_existing=True,
            )
            self._topic_jobs.append(job)
            self.logger.info(
                f"[{self.phone_number}] Scheduled topic {slot} '{topic_name}' at {hour:02d}:{minute:02d} ({timezone_str})"
            )

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    async def start(self):
        # Phase 4: Wire the incoming message handler BEFORE connecting
        async def raw_message_logger(c, m):
            try:
                sender_jid = getattr(m.Info.MessageSource, "Sender", None)
                sender = getattr(sender_jid, "User", "Unknown") if sender_jid else "Unknown"
                chat_jid = getattr(m.Info.MessageSource, "Chat", None)
                chat = getattr(chat_jid, "User", "Unknown") if chat_jid else "Unknown"
                is_from_me = getattr(m.Info.MessageSource, "IsFromMe", False)
                text = (getattr(m.Message, "conversation", "") or getattr(getattr(m.Message, "extendedTextMessage", None), "text", "") or "")
                self.logger.info(f"RAW MESSAGE EVENT: chat={chat}, sender={sender}, is_from_me={is_from_me}, text='{text[:30]}'")
            except Exception as e:
                self.logger.error(f"Error logging raw message: {e}")
            await self.handle_incoming(c, m)

        self.whatsapp.register_incoming_handler(
            handler=lambda c, m: asyncio.create_task(raw_message_logger(c, m))
        )
        self.logger.info(f"[{self.phone_number}] Incoming message handler registered.")

        await self.whatsapp.connect()

        self.config = ConfigManager.load_config(self.phone_number)
        timezone_str = getattr(self.config, "timezone", "UTC")

        # Per-topic cron jobs
        self._register_topic_jobs(self.config, timezone_str)

        # Phase 6: Weekly report — every Sunday at 09:00 in user's timezone
        self.weekly_job = self.scheduler.add_job(
            self.weekly_report_task,
            trigger="cron",
            day_of_week="sun",
            hour=9,
            minute=0,
            timezone=timezone_str,
        )

        self.scheduler.start()
        self.logger.info(f"✅ [{self.phone_number}] Scheduler started with per-topic times.")

        asyncio.create_task(self._watch_config())

    async def _watch_config(self):
        """Background task that polls for config changes every 60s and hot-reloads jobs."""
        last_snapshot = self.config.model_dump()

        while True:
            await asyncio.sleep(60)
            try:
                new_cfg = ConfigManager.load_config(self.phone_number)
                new_snapshot = new_cfg.model_dump()

                if new_snapshot != last_snapshot:
                    self.logger.info(f"🔄 [{self.phone_number}] Config change detected — hot-reloading per-topic jobs...")
                    new_tz = getattr(new_cfg, "timezone", "UTC")
                    self.config = new_cfg
                    self.level = new_cfg.level
                    self.skill_profile = new_cfg.skill_profile
                    self.created_at = new_cfg.created_at
                    last_snapshot = new_snapshot

                    # Remove old topic jobs and re-register
                    for job in getattr(self, "_topic_jobs", []):
                        try:
                            job.remove()
                        except Exception:
                            pass
                    self._register_topic_jobs(new_cfg, new_tz)

                    # Reschedule weekly report timezone
                    self.weekly_job.reschedule(
                        trigger="cron",
                        day_of_week="sun",
                        hour=9,
                        minute=0,
                        timezone=new_tz,
                    )
                    self.logger.info(f"✅ [{self.phone_number}] Per-topic jobs hot-reloaded.")
            except Exception as e:
                self.logger.error(f"Config watch error: {e}")

