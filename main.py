import asyncio
import sys
from src.core.env import load_env, get_interview_topic, require_llm_key
from src.core.config import ConfigManager
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

    # Keep this user's concurrent task alive
    while True:
        await asyncio.sleep(60)
        logger.debug(f"Heartbeat — {phone_number}")

async def main():
    """Main entry point — orchestration of all registered users."""
    load_env()
    
    logger.info("---------------------------------------------")
    logger.info("      OpenClaw Multi-User Bot Daemon         ")
    logger.info("---------------------------------------------")

    # Validate LLM keys early
    try:
        require_llm_key()
    except ValueError as e:
        logger.error(f"FATAL: {e}")
        sys.exit(1)

    shared_topic = get_interview_topic()

    # Discover all registered users
    users = ConfigManager.get_all_users()
    if not users:
        logger.warning("⚠️ No users registered yet. Add users via the Streamlit dashboard.")
        logger.info("Waiting for first registration... (polling every 30s)")
        while True:
            await asyncio.sleep(30)
            users = ConfigManager.get_all_users()
            if users:
                logger.info(f"✅ Found {len(users)} registered users. Starting...")
                break

    logger.info(f"📋 Initializing bots for: {users}")

    # Launch concurrent tasks for all registered users
    tasks = [asyncio.create_task(run_user_bot(phone, shared_topic)) for phone in users]

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
