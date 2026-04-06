import os
import asyncio
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.agent import InterviewAgent
from src.whatsapp_client import WhatsAppClient

load_dotenv()


class InterviewScheduler:
    def __init__(self, agent, whatsapp):
        self.agent = agent
        self.whatsapp = whatsapp
        self.scheduler = AsyncIOScheduler()
        self.schedule_time = os.getenv("SCHEDULE_TIME", "06:00")

    async def daily_task(self):
        print("🚀 Starting fresh content delivery cycle (Daily at 06:00)")
        
        # 1. Generate textual Challenge and Solution (History-aware)
        detailed_text, image_prompt = await self.agent.get_daily_challenge()
        
        # 2. Send the detailed text solution first
        await self.whatsapp.send_message(detailed_text)
        await asyncio.sleep(2)
        
        # 3. Generate the architectural diagram using DALL-E 3
        image_path = await self.agent.llm.generate_image(image_prompt)
        if image_path:
            await self.whatsapp.send_image(image_path, caption="Visual Diagram for the Challenge")
            await asyncio.sleep(5)

        # 4. Generate Fresh Medium/News (Simulated search results for autonomy)
        # In a production setting, this would call a real search API.
        # For now, we use the LLM to generate 'likely' current topics to ensure variety.
        medium_summary = await self.agent.get_curated_content("medium_posts", "Current trends in Agentic AI and ML Deployment as of April 2026.")
        await self.whatsapp.send_message(f"*Part 2: Fresh Medium Reads*\n\n{medium_summary}")
        await asyncio.sleep(5)
        
        news_summary = await self.agent.get_curated_content("Tech_news", "Top global tech news for today.")
        await self.whatsapp.send_message(f"*Part 3: Trending Tech News*\n\n{news_summary}")
        await asyncio.sleep(5)
        
        global_news_summary = await self.agent.get_curated_content("Global_news", "Top global news for today.")
        await self.whatsapp.send_message(f"*Part 4: Trending Global News*\n\n{global_news_summary}")
            
        print("✅ Fresh content loop completed.")

    async def start(self):
        await self.whatsapp.connect()
        self.whatsapp.register_incoming_handler()

        hour, minute = map(int, self.schedule_time.split(":"))

        self.scheduler.add_job(
            self.daily_task,
            trigger="cron",
            hour=hour,
            minute=minute,
        )

        self.scheduler.start()
        print(f"✅ Scheduler started for daily delivery at {self.schedule_time}")

        while True:
            await asyncio.sleep(3600)


async def main():
    agent = InterviewAgent("Senior Java + Kafka + Spring Boot")
    whatsapp = WhatsAppClient()
    scheduler = InterviewScheduler(agent, whatsapp)
    await scheduler.start()


if __name__ == "__main__":
    asyncio.run(main())