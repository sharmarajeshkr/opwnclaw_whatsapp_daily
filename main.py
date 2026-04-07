import os
import asyncio
import sys
from dotenv import load_dotenv
from src.agent import InterviewAgent
from src.whatsapp_client import WhatsAppClient
from src.scheduler import InterviewScheduler

# For logging
import logging
logging.basicConfig(level=logging.INFO)

load_dotenv()

async def main():
    """Main entry point for the Interview Question WhatsApp Bot."""
    print("---------------------------------------------")
    print("      Interview Bot - OpenClaw      ")
    print("---------------------------------------------")
    
    # Check for API keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    if not (gemini_key or openai_key):
        print("ERROR: Please set GEMINI_API_KEY or OPENAI_API_KEY in .env file.")
        sys.exit(1)

    # Initialize components
    agent = InterviewAgent(topic=os.getenv("INTERVIEW_TOPIC", "Software Engineering"))
    whatsapp = WhatsAppClient(session_name=os.getenv("WHATSAPP_SESSION_NAME", "interview_bot"))
    
    # 1. Start WhatsApp connection
    print("\n---------------------------------------------")
    print("ACTION REQUIRED: Scan the QR code below!")
    print("---------------------------------------------")
    print("DEBUG: Starting WhatsApp connection...", flush=True)
    await whatsapp.connect()
    
    # 2. Wait for initialization (QR code scan if needed, and initial sync)
    print("DEBUG: Waiting for initialization and background sync sleep(30)...", flush=True)
    await asyncio.sleep(30)
    
    # 3. Setup and start the daily scheduler
    print("\nInitializing Daily Scheduler...", flush=True)
    scheduler = InterviewScheduler(agent, whatsapp)
    
    # Send an initial test message to confirm connection
    print("\nSending an initial greeting to confirm connection...", flush=True)
    await scheduler.daily_task()
    
    await scheduler.start()

    
    # 4. Success message
    print("\n---------------------------------------------")
    print("BOT IS ACTIVE AND RUNNING!")
    print(f"Location: c:\\openClaw_Interview")
    print(f"Log: Scheduled for {os.getenv('SCHEDULE_TIME', '09:00')} daily.")
    print("---------------------------------------------")
    
    # Keep the main thread alive
    try:
        while True:
            await asyncio.sleep(60)  # Wake up every minute
            print("DEBUG: Scheduler heartbeat - Waiting for next daily update...", flush=True)
    except KeyboardInterrupt:
        print("\nBot stopped by user.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
