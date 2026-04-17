import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.content.agent import InterviewAgent
from src.bot.client import WhatsAppClient
from src.bot.sender import ChannelSender
from src.core.config import ConfigManager
from src.core.session import SessionManager
from src.core.performance import PerformanceTracker
from src.core.logger import get_logger
from src.mcp.client import run_medium_query

logger = get_logger("InterviewScheduler")


class InterviewScheduler:
    def __init__(self, agent: InterviewAgent, whatsapp: WhatsAppClient, phone_number: str):
        self.agent = agent
        self.whatsapp = whatsapp
        self.phone_number = phone_number
        self.sender = ChannelSender(whatsapp, phone_number)
        self.scheduler = AsyncIOScheduler()
        self.config = ConfigManager.load_config(phone_number)
        self.schedule_time = self.config.schedule_time

    # ------------------------------------------------------------------
    # Phase 5 — Weakness-Aware Daily Task
    # ------------------------------------------------------------------

    async def daily_task(self):
        logger.info(f"🚀 [{self.phone_number}] Starting content delivery cycle")

        # Clear any stale unanswered session from yesterday so scoring
        # doesn't accidentally apply to the wrong question.
        SessionManager.clear_all_stale(self.phone_number)

        self.sender.refresh_config()
        config = self.sender.config
        topics = config.topics

        # 1. Architecture Challenge
        if topics.topic_1:
            detailed_text, image_prompt = await self.agent.get_daily_challenge()
            image_path = await self.agent.llm.generate_image(image_prompt)
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
            logger.info(
                f"[{self.phone_number}] Weak topics prioritised: {weak_topics} "
                f"→ selected: {selected_topics}"
            )

        for topic in selected_topics:
            # get_deep_dive_with_question returns (question_text, full_message)
            # We store the question in SessionManager for later scoring.
            question, full_content = await self.agent.get_deep_dive_with_question(topic)
            SessionManager.set_active_question(self.phone_number, question, topic)

            await self.sender.send_to_all(full_content, title=f"Deep Dive: {topic}")
            await asyncio.sleep(5)

        # 4. Fresh Updates 1
        if topics.topic_4:
            content = await self.agent.get_curated_content(
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
                
                content = await self.agent.get_curated_content("Medium_updates", prompt)
                await self.sender.send_to_all(content, title=f"Latest from Medium: {topics.topic_5}")
            except Exception as e:
                logger.error(f"MCP Integration Error for {topics.topic_5}: {e}")
                # Fallback to pure LLM if MCP server crashes
                content = await self.agent.get_curated_content(
                    "Global_news", f"Top global news about {topics.topic_5} for today."
                )
                await self.sender.send_to_all(content, title=f"Fresh Updates: {topics.topic_5}")

        logger.info(f"✅ [{self.phone_number}] Content delivery cycle completed.")

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

            logger.info(f"📩 [{phone}] Incoming reply: {text}")

            # ── Look up active session ─────────────────────────────────
            session = SessionManager.get_active_session(phone)
            if not session:
                logger.debug(f"[{phone}] No active session — ignoring reply.")
                
                # Send a gentle fallback message so the user knows the bot is alive
                fallback_msg = (
                    "🤖 *OpenClaw Coach*\n\n"
                    "I don't have an active question pending for you right now!\n"
                    "Wait for your next daily delivery to answer and get scored. 🚀"
                )
                await self.whatsapp.send_message(fallback_msg)
                return

            # ── Score with LLM ─────────────────────────────────────────
            logger.info(f"[{phone}] Scoring answer for topic='{session['topic']}'...")
            result = await self.agent.evaluate_answer(
                question=session["question"],
                user_answer=text,
                topic=session["topic"],
            )

            # ── Persist to DB ──────────────────────────────────────────
            PerformanceTracker.record_score(
                phone=phone,
                topic=session["topic"],
                score=result["score"],
                weak_aspects=result["weak_aspects"],
                feedback=result["feedback"],
            )
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

            feedback_msg = (
                f"{emoji} *Score: {score}/10 — {verdict}*\n\n"
                f"{result['feedback']}"
            )
            if result["weak_aspects"]:
                aspects = ", ".join(result["weak_aspects"])
                feedback_msg += f"\n\n📌 *Review these concepts:* {aspects}"

            await self.whatsapp.send_message(feedback_msg)
            logger.info(f"✅ [{phone}] Feedback sent — score {score}/10")

        except Exception as exc:
            logger.error(f"handle_incoming error: {exc}", exc_info=True)

    # ------------------------------------------------------------------
    # Phase 6 — Weekly Report (Every Sunday 09:00)
    # ------------------------------------------------------------------

    async def weekly_report_task(self):
        """Send a weekly performance summary every Sunday morning."""
        logger.info(f"📊 [{self.phone_number}] Generating weekly report...")

        summary = PerformanceTracker.get_weekly_summary(self.phone_number)

        if not summary:
            msg = (
                "📊 *Weekly Report*\n\n"
                "No answers recorded this week.\n"
                "Reply to the daily questions to track your progress! 💬"
            )
            await self.whatsapp.send_message(msg)
            return

        lines = ["📊 *Weekly Performance Report*", "─────────────────────────"]

        for row in summary:
            avg = row["avg_score"]
            if avg >= 8:
                icon = "🏆"
            elif avg >= 6:
                icon = "✅"
            else:
                icon = "⚠️"
            lines.append(
                f"{icon} *{row['topic']}*\n"
                f"   Avg: {avg}/10  |  Attempts: {row['attempts']}  "
                f"|  Best: {row['max_score']}  |  Worst: {row['min_score']}"
            )

        weak = [r["topic"] for r in summary if r["avg_score"] < 6]
        total_attempts = sum(r["attempts"] for r in summary)

        lines.append("─────────────────────────")
        lines.append(f"📝 *Total answered this week:* {total_attempts} questions")

        if weak:
            lines.append(f"🔥 *Drill more this week:* {', '.join(weak)}")
        else:
            lines.append("🎯 All topics above threshold — keep it up!")

        await self.whatsapp.send_message("\n".join(lines))
        logger.info(f"✅ [{self.phone_number}] Weekly report sent.")

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    async def start(self):
        # Phase 4: Wire the incoming message handler BEFORE connecting
        # We add a wrapper to log EVERY message event that neonize fires
        async def raw_message_logger(c, m):
            try:
                sender_jid = getattr(m.Info.MessageSource, "Sender", None)
                sender = getattr(sender_jid, "User", "Unknown") if sender_jid else "Unknown"
                
                chat_jid = getattr(m.Info.MessageSource, "Chat", None)
                chat = getattr(chat_jid, "User", "Unknown") if chat_jid else "Unknown"
                
                is_from_me = getattr(m.Info.MessageSource, "IsFromMe", False)
                text = (getattr(m.Message, "conversation", "") or getattr(getattr(m.Message, "extendedTextMessage", None), "text", "") or "")
                logger.info(f"RAW MESSAGE EVENT: chat={chat}, sender={sender}, is_from_me={is_from_me}, text='{text[:30]}'")
            except Exception as e:
                logger.error(f"Error logging raw message: {e}")
            await self.handle_incoming(c, m)

        self.whatsapp.register_incoming_handler(
            handler=lambda c, m: asyncio.create_task(raw_message_logger(c, m))
        )
        logger.info(f"[{self.phone_number}] Incoming message handler registered.")

        await self.whatsapp.connect()

        self.config = ConfigManager.load_config(self.phone_number)
        self.schedule_time = self.config.schedule_time
        hour, minute = map(int, self.schedule_time.split(":"))
        timezone_str = getattr(self.config, "timezone", "UTC")

        # Daily content delivery
        self.daily_job = self.scheduler.add_job(
            self.daily_task,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=timezone_str,
        )

        # Phase 6: Weekly report — every Sunday at 09:00
        # By default we use the same user's timezone, or leave it hardcoded to 9AM in their timezone
        self.weekly_job = self.scheduler.add_job(
            self.weekly_report_task,
            trigger="cron",
            day_of_week="sun",
            hour=9,
            minute=0,
            timezone=timezone_str,
        )

        self.scheduler.start()
        logger.info(
            f"✅ [{self.phone_number}] Scheduler started — "
            f"daily at {self.schedule_time} ({timezone_str})"
        )

        # Start background task to hot-reload config changes
        asyncio.create_task(self._watch_config())

    async def _watch_config(self):
        """Background task that polls for config changes and hot-reloads the scheduler."""
        while True:
            await asyncio.sleep(60)  # Check every 1 minute
            try:
                new_cfg = ConfigManager.load_config(self.phone_number)
                new_tz = getattr(new_cfg, "timezone", "UTC")
                
                if new_cfg.schedule_time != self.schedule_time or new_tz != getattr(self.config, "timezone", "UTC"):
                    logger.info(f"🔄 [{self.phone_number}] Config change detected. Hot-reloading scheduler...")
                    self.config = new_cfg
                    self.schedule_time = new_cfg.schedule_time
                    hour, minute = map(int, self.schedule_time.split(":"))

                    self.daily_job.reschedule(
                        trigger="cron",
                        hour=hour,
                        minute=minute,
                        timezone=new_tz
                    )
                    self.weekly_job.reschedule(
                        trigger="cron",
                        day_of_week="sun",
                        hour=9,
                        minute=0,
                        timezone=new_tz
                    )
                    logger.info(f"✅ [{self.phone_number}] Scheduler hot-reloaded to {self.schedule_time} ({new_tz})")
            except Exception as e:
                logger.error(f"Error checking config for hot-reload: {e}")
