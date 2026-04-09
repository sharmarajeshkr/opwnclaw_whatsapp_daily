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

        # 5. Fresh Updates 2
        if topics.topic_5:
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
            # ── Extract sender JID → phone number ──────────────────────
            sender_jid = str(message_ev.Info.MessageSource.Sender)
            phone = sender_jid.split("@")[0]

            # ── Extract plain text ─────────────────────────────────────
            msg = message_ev.Message
            text = (
                getattr(msg, "Conversation", "")
                or getattr(getattr(msg, "ExtendedTextMessage", None), "Text", "")
                or ""
            ).strip()

            if not text:
                return  # Ignore media, stickers, reactions

            logger.info(f"📩 [{phone}] Incoming reply: {text[:80]}...")

            # ── Look up active session ─────────────────────────────────
            session = SessionManager.get_active_session(phone)
            if not session:
                logger.debug(f"[{phone}] No active session — ignoring reply.")
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
            SessionManager.clear_session(phone)

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
        await self.whatsapp.connect()

        # Phase 4: Wire the incoming message handler
        self.whatsapp.register_incoming_handler(
            handler=lambda c, m: asyncio.create_task(self.handle_incoming(c, m))
        )
        logger.info(f"[{self.phone_number}] Incoming message handler registered.")

        self.config = ConfigManager.load_config(self.phone_number)
        self.schedule_time = self.config.schedule_time
        hour, minute = map(int, self.schedule_time.split(":"))

        # Daily content delivery
        self.scheduler.add_job(
            self.daily_task,
            trigger="cron",
            hour=hour,
            minute=minute,
        )

        # Phase 6: Weekly report — every Sunday at 09:00
        self.scheduler.add_job(
            self.weekly_report_task,
            trigger="cron",
            day_of_week="sun",
            hour=9,
            minute=0,
        )

        self.scheduler.start()
        logger.info(
            f"✅ [{self.phone_number}] Scheduler started — "
            f"daily at {self.schedule_time}, weekly report Sundays 09:00"
        )
