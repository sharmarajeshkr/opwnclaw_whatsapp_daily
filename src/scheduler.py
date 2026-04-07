import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.agent import InterviewAgent
from src.whatsapp_client import WhatsAppClient
from src.channel_sender import ChannelSender
from src.config_manager import ConfigManager
from src.logger_config import get_logger
logger = get_logger(os.path.basename(__file__) if "__file__" in locals() else "OpenClawBot")


class InterviewScheduler:
    def __init__(self, agent, whatsapp):
        self.agent = agent
        self.whatsapp = whatsapp
        self.sender = ChannelSender(whatsapp)
        self.scheduler = AsyncIOScheduler()
        self.config = ConfigManager.load_config()
        self.schedule_time = self.config.get("schedule_time", "06:00")

    async def daily_task(self):
        logger.info(f"🚀 Starting configuration-driven content delivery cycle")
        
        self.sender.refresh_config()
        config = self.sender.config
        topics = config.get("topics", {})
        
        # 1. Architecture Challenge
        topic_1 = topics.get("topic_1", "Architecture Challenge")
        if topic_1:
            detailed_text, image_prompt = await self.agent.get_daily_challenge()
            image_path = await self.agent.llm.generate_image(image_prompt)
            await self.sender.send_to_all(detailed_text, image_path, "Visual Diagram for the Challenge", title=topic_1)
            await asyncio.sleep(5)
            
        # 2. Deep Dive Subject 1
        topic_2 = topics.get("topic_2", "Kafka")
        if topic_2:
            content = await self.agent.get_deep_dive(topic_2)
            await self.sender.send_to_all(content, title=f"Deep Dive: {topic_2}")
            await asyncio.sleep(5)
            
        # 3. Deep Dive Subject 2
        topic_3 = topics.get("topic_3", "Agentic AI")
        if topic_3:
            content = await self.agent.get_deep_dive(topic_3)
            await self.sender.send_to_all(content, title=f"Deep Dive: {topic_3}")
            await asyncio.sleep(5)
            
        # 4. Fresh Updates 1
        topic_4 = topics.get("topic_4", "AI News")
        if topic_4:
            content = await self.agent.get_curated_content("Tech_news", f"Top global news about {topic_4} for today.")
            await self.sender.send_to_all(content, title=f"Fresh Updates: {topic_4}")
            await asyncio.sleep(5)
            
        # 5. Fresh Updates 2
        topic_5 = topics.get("topic_5", "Latest Global News")
        if topic_5:
            content = await self.agent.get_curated_content("Global_news", f"Top global news about {topic_5} for today.")
            await self.sender.send_to_all(content, title=f"Fresh Updates: {topic_5}")
            
        logger.info("✅ Fresh content loop completed.")

    async def start(self):
        await self.whatsapp.connect()
        self.whatsapp.register_incoming_handler()

        # Update schedule_time from fresh config before adding job
        self.config = ConfigManager.load_config()
        self.schedule_time = self.config.get("schedule_time", "06:00")
        hour, minute = map(int, self.schedule_time.split(":"))

        self.scheduler.add_job(
            self.daily_task,
            trigger="cron",
            hour=hour,
            minute=minute,
        )

        self.scheduler.start()
        logger.info(f"✅ Scheduler started for daily delivery at {self.schedule_time}")