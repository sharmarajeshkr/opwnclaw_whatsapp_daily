import os
import asyncio
import sys
from dotenv import load_dotenv
from src.agent import InterviewAgent
from src.whatsapp_client import WhatsAppClient
from src.scheduler import InterviewScheduler

# For logging
import logging
from src.logger_config import get_logger
logger = get_logger(os.path.basename(__file__) if "__file__" in locals() else "OpenClawBot")

logging.basicConfig(level=logging.INFO)

load_dotenv()

async def main():
    """Main entry point for the Interview Question WhatsApp Bot."""
    logger.info("---------------------------------------------")
    logger.info("      Interview Bot - OpenClaw      ")
    logger.info("---------------------------------------------")
    
    # Check for API keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    if not (gemini_key or openai_key):
        logger.error("ERROR: Please set GEMINI_API_KEY or OPENAI_API_KEY in .env file.")
        sys.exit(1)

    # Initialize components
    agent = InterviewAgent(topic=os.getenv("INTERVIEW_TOPIC", "Software Engineering"))
    whatsapp = WhatsAppClient(session_name=os.getenv("WHATSAPP_SESSION_NAME", "interview_bot"))
    
    # 1. Start WhatsApp connection
    logger.info("\n---------------------------------------------")
    logger.info("ACTION REQUIRED: Scan the QR code below!")
    logger.info("---------------------------------------------")
    logger.debug("DEBUG: Starting WhatsApp connection...")
    await whatsapp.connect()
    
    # 2. Wait for initialization (QR code scan if needed, and initial sync)
    logger.debug("DEBUG: Waiting for initialization and background sync sleep(30)...")
    await asyncio.sleep(30)
    
    # 3. Setup and start the daily scheduler
    logger.info("\nInitializing Daily Scheduler...")
    scheduler = InterviewScheduler(agent, whatsapp)
    
    # Send an initial test message to confirm connection
    logger.info("\nSending an initial greeting to confirm connection...")
    await scheduler.daily_task()
    
    await scheduler.start()

    
    # 4. Success message
    logger.info("\n---------------------------------------------")
    logger.info("BOT IS ACTIVE AND RUNNING!")
    logger.info(f"Location: c:\\openClaw_Interview")
    logger.info(f"Log: Scheduled for {scheduler.schedule_time} daily.")
    logger.info("---------------------------------------------")
    
    # Keep the main thread alive
    try:
        while True:
            await asyncio.sleep(60)  # Wake up every minute
            logger.debug("DEBUG: Scheduler heartbeat - Waiting for next daily update...")
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
