"""
main.py
-------
Main entry point for the Interview Multi-User Bot Daemon.
Orchestrates connectivity and scheduling for all registered and paired users.
"""
import asyncio
import sys
import os
import argparse

from app.core.config import settings, ConfigManager
from app.database.db import init_db
from app.core.logging import get_logger
from app.channels.whatsapp.client import WhatsAppClient
from app.services.scheduler import InterviewScheduler
from app.core.utils import is_user_paired

logger = get_logger("Main")

async def run_user_bot(phone_number: str):
    """Initialize and run WhatsApp bot + scheduler for a single user."""
    logger.info(f"🚀 Initializing bot for user: {phone_number}")
    
    # Initialize the client first
    whatsapp = WhatsAppClient(phone_number=phone_number)
    
    # The Scheduler now handles its own specialized agents internally
    scheduler = InterviewScheduler(whatsapp, phone_number=phone_number)
    
    await scheduler.start()

    # ── Send first batch immediately on first run ─────────────────────────
    # Check if content has already been sent today. If not, fire right away
    # so the user doesn't have to wait until the scheduled cron time.
    try:
        from app.database.db import get_conn
        import datetime
        today = datetime.date.today().isoformat()
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM performance_scores "
                "WHERE phone_number = %s AND answered_at >= %s",
                (phone_number, today)
            ).fetchone()
        already_delivered = (row["cnt"] > 0) if row else False
        if not already_delivered:
            logger.info(f"[{phone_number}] First run detected — sending immediate content delivery.")
            await asyncio.sleep(5)  # brief pause to let WhatsApp settle
            await scheduler.daily_task()
    except Exception as e:
        logger.error(f"[{phone_number}] Immediate delivery error: {e}")

    # Monitor connection and keep the task alive
    while True:
        await asyncio.sleep(60)
        logger.debug(f"Heartbeat — {phone_number} (Connected: {whatsapp.connected})")
        if not whatsapp.connected:
            logger.warning(f"🔄 [{phone_number}] Connection drop detected. Reconnecting...")
            try:
                await whatsapp.connect()
            except Exception as e:
                logger.error(f"❌ [{phone_number}] Reconnect failed: {e}")


async def main():
    """System entry point — orchestration of paired users."""
    parser = argparse.ArgumentParser(description="Interview WhatsApp Bot Daemon")
    parser.add_argument("--phone", type=str, help="Phone number for a single user bot (digits only)")
    args = parser.parse_args()

    # Initialize PostgreSQL schema
    init_db()
    
    logger.info("=============================================")
    logger.info("      Interview Multi-User Bot Daemon         ")
    logger.info("=============================================")

    # Security check: Ensure LLM keys are present
    if not settings.OPENAI_API_KEY and not settings.GEMINI_API_KEY:
        logger.error("FATAL: No LLM API keys found in environment (OPENAI_API_KEY or GEMINI_API_KEY).")
        sys.exit(1)

    if args.phone:
        # Single user mode (often used for debugging or manual starts)
        phone = args.phone.strip().lstrip("+")
        await run_user_bot(phone)
    else:
        # Multi-user mode (default)
        logger.info("Scanning for paired users...")
        while True:
            all_users = ConfigManager.get_all_users()
            paired_users = [u for u in all_users if is_user_paired(u)]
            
            if not paired_users:
                logger.info("⏳ No paired users found. Polling every 30s...")
                await asyncio.sleep(30)
            else:
                logger.info(f"✅ Found {len(paired_users)} paired users: {paired_users}")
                break

        # Launch concurrent bot tasks
        tasks = [asyncio.create_task(run_user_bot(phone)) for phone in paired_users]
        logger.info(f"🚀 {len(tasks)} user bots are now active.")

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received.")

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
