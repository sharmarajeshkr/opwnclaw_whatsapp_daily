import os
import asyncio
import sys
from dotenv import load_dotenv
from src.agent import InterviewAgent
from src.whatsapp_client import WhatsAppClient
from src.scheduler import InterviewScheduler
from src.config_manager import ConfigManager

import logging
from src.logger_config import get_logger
logger = get_logger(os.path.basename(__file__) if "__file__" in locals() else "OpenClawBot")

logging.basicConfig(level=logging.INFO)

load_dotenv()


async def run_user_bot(phone_number: str, agent: InterviewAgent):
    """Initialize and run WhatsApp bot + scheduler for a single user."""
    logger.info(f"🚀 Starting bot for user: {phone_number}")
    whatsapp = WhatsAppClient(phone_number=phone_number)
    scheduler = InterviewScheduler(agent, whatsapp, phone_number=phone_number)
    await scheduler.start()

    # Keep this user's task alive
    while True:
        await asyncio.sleep(60)
        logger.debug(f"💓 Heartbeat — {phone_number}")


async def main():
    """Main entry point — spins up a bot for every registered user."""
    logger.info("---------------------------------------------")
    logger.info("      OpenClaw Multi-User Bot Daemon         ")
    logger.info("---------------------------------------------")

    # Check for API keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    if not (gemini_key or openai_key):
        logger.error("ERROR: Please set GEMINI_API_KEY or OPENAI_API_KEY in .env file.")
        sys.exit(1)

    # Shared agent (stateless, safe to reuse across users)
    agent = InterviewAgent(topic=os.getenv("INTERVIEW_TOPIC", "Software Engineering"))

    # Discover all registered users
    users = ConfigManager.get_all_users()
    if not users:
        logger.warning("⚠️  No users registered yet. Add users via the Streamlit dashboard.")
        logger.info("Waiting for users to be registered... (polling every 30s)")
        while True:
            await asyncio.sleep(30)
            users = ConfigManager.get_all_users()
            if users:
                logger.info(f"✅ Found {len(users)} registered user(s). Starting bots...")
                break

    logger.info(f"📋 Registered users: {users}")

    # Launch a concurrent task per user
    tasks = [asyncio.create_task(run_user_bot(phone, agent)) for phone in users]

    logger.info(f"✅ {len(tasks)} user bot(s) active and running!")

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
