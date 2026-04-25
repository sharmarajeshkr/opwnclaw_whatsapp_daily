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

    if args.phone:
        # SINGLE USER MODE: Run bot directly in this process
        phone = args.phone.strip().lstrip("+")
        await run_user_bot(phone)
    else:
        # MULTI-USER DAEMON MODE: Manage per-user subprocesses
        from app.core.utils import start_bot, is_bot_running
        logger.info("🚀 System started in Daemon Mode. Monitoring users...")
        
        while True:
            try:
                all_users = ConfigManager.get_all_users()
                paired_users = [u for u in all_users if is_user_paired(u)]
                
                for phone in paired_users:
                    if not is_bot_running(phone):
                        logger.info(f"🆕 New/Idle paired user found: {phone}. Launching isolation process...")
                        start_bot(phone)
                        # Small stagger to prevent DB connection spikes
                        await asyncio.sleep(2)
                
                # Poll for new users every 30 seconds
                await asyncio.sleep(30)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Daemon management error: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Stopping daemon.")

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
