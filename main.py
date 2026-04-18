import asyncio
import sys
import os
from src.core.sys_config import settings
from src.core.config import ConfigManager
from src.core.db import init_db
from src.core.logger import get_logger
from src.content.agent import InterviewAgent
from src.bot.client import WhatsAppClient
from src.scheduling.scheduler import InterviewScheduler

logger = get_logger("Main")

async def run_user_bot(phone_number: str, shared_topic: str):
    """Initialize and run WhatsApp bot + scheduler for a single user."""
    logger.info(f"🚀 Initializing bot for user: {phone_number}")
    
    # Each user gets their own agent instance (with their own history)
    agent = InterviewAgent(phone_number=phone_number, topic=shared_topic)
    whatsapp = WhatsAppClient(phone_number=phone_number)
    scheduler = InterviewScheduler(agent, whatsapp, phone_number=phone_number)
    
    await scheduler.start()

    # Keep this user's concurrent task alive and monitor connection
    while True:
        await asyncio.sleep(60)
        logger.debug(f"Heartbeat — {phone_number} (Connected: {whatsapp.connected})")
        if not whatsapp.connected:
            logger.warning(f"🔄 [{phone_number}] Connection drop detected in heartbeat. Reconnecting...")
            try:
                await whatsapp.connect()
            except Exception as e:
                logger.error(f"❌ [{phone_number}] Reconnect failed: {e}")

import argparse

async def main():
    """Main entry point — orchestration of all registered users."""
    parser = argparse.ArgumentParser(description="OpenClaw WhatsApp Bot Daemon")
    parser.add_argument("--phone", type=str, help="Phone number for a single user bot")
    args = parser.parse_args()

    # Initialise the coach SQLite DB (creates coach.db + tables if not present)
    init_db()
    
    logger.info("---------------------------------------------")
    logger.info("      OpenClaw Multi-User Bot Daemon         ")
    logger.info("---------------------------------------------")

    # Validate LLM keys early
    if not settings.OPENAI_API_KEY and not settings.GEMINI_API_KEY:
        logger.error("FATAL: Neither OPENAI_API_KEY nor GEMINI_API_KEY is set in the environment.")
        sys.exit(1)

    shared_topic = settings.INTERVIEW_TOPIC

    if args.phone:
        # Single user mode
        phone = args.phone.strip().lstrip("+")
        await run_user_bot(phone, shared_topic)
    else:
        # All users mode (default)
        while True:
            all_users = ConfigManager.get_all_users()
            from src.core.utils import is_user_paired
            paired_users = [u for u in all_users if is_user_paired(u)]
            
            if not paired_users:
                logger.warning("⚠️ No paired users found. Add and pair users via the Streamlit dashboard.")
                logger.info("Waiting for a user to be paired... (polling every 30s)")
                await asyncio.sleep(30)
            else:
                logger.info(f"✅ Found {len(paired_users)} paired users. Starting...")
                break

        logger.info(f"📋 Initializing bots for paired users: {paired_users}")

        # Launch concurrent tasks for all paired users
        tasks = [asyncio.create_task(run_user_bot(phone, shared_topic)) for phone in paired_users]

        logger.info(f"✅ {len(tasks)} user bots are now active.")

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Termination signal received. Shutting down...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
