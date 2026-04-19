import asyncio
import datetime
from src.core.db import get_conn
from src.core.performance import PerformanceTracker
from src.content.agent import InterviewAgent
from src.bot.client import WhatsAppClient
from src.scheduling.scheduler import InterviewScheduler

async def main():
    phone = '919876543210'
    
    # 1. Setup Advanced Level
    with get_conn() as conn:
        conn.execute("UPDATE user_configs SET level = 'Advanced' WHERE phone_number = %s", (phone,))
    
    # 2. Record high scores
    tracker = PerformanceTracker()
    tracker.record_score(phone, "Kafka", 10, ["none"], "Excellent depth.")
    tracker.record_score(phone, "Kafka", 9, ["none"], "Very good.")
    
    # 3. Trigger Weekly Report
    agent = InterviewAgent(phone)
    client = WhatsAppClient(phone)
    # Mock send_message to avoid actual WhatsApp API call and loop issues
    client.send_message = asyncio.CoroutineMock() if hasattr(asyncio, 'CoroutineMock') else None
    if not client.send_message:
        async def mock_send(msg):
            # Strip emojis for console printing to avoid UnicodeEncodeError
            clean_msg = msg.encode('ascii', 'ignore').decode('ascii')
            print(f"\n--- WHATSAPP MESSAGE START ---\n{clean_msg}\n--- WHATSAPP MESSAGE END ---\n")
        client.send_message = mock_send

    sched = InterviewScheduler(agent, client, phone)
    await sched.weekly_report_task()

if __name__ == "__main__":
    asyncio.run(main())
