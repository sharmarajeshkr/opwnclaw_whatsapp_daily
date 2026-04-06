import os
import asyncio
from dotenv import load_dotenv
from src.agent import InterviewAgent
from src.whatsapp_client import WhatsAppClient
from src.scheduler import InterviewScheduler

load_dotenv()

async def main():
    print("--- Multi-Modal Delivery Test ---")
    
    # Initialize components
    agent = InterviewAgent()
    whatsapp = WhatsAppClient()
    scheduler = InterviewScheduler(agent, whatsapp)
    
    # Start connection
    await whatsapp.connect()
    
    # Wait for sync
    print("Waiting 15 seconds for sync...")
    await asyncio.sleep(15)
    
    # Trigger the multi-modal task
    try:
        await scheduler.daily_task()
        print("\nSUCCESS: Multi-modal test finished.")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
