import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.content.agent import InterviewAgent
from src.bot.client import WhatsAppClient
from src.bot.sender import ChannelSender
from src.core.config import ConfigManager
from src.core.logger import get_logger

logger = get_logger("InterviewScheduler")

class InterviewScheduler:
    def __init__(self, agent: InterviewAgent, whatsapp: WhatsAppClient, phone_number: str):
        self.agent = agent
        self.whatsapp = whatsapp
        self.phone_number = phone_number
        self.sender = ChannelSender(whatsapp, phone_number)
        self.scheduler = AsyncIOScheduler()
        self.config = ConfigManager.load_config(phone_number)
        self.schedule_time = self.config.schedule_time

    async def daily_task(self):
        logger.info(f"🚀 [{self.phone_number}] Starting content delivery cycle")
        
        self.sender.refresh_config()
        config = self.sender.config
        topics = config.topics
        
        # 1. Architecture Challenge
        if topics.topic_1:
            detailed_text, image_prompt = await self.agent.get_daily_challenge()
            image_path = await self.agent.llm.generate_image(image_prompt)
            await self.sender.send_to_all(detailed_text, image_path, "Visual Diagram for the Challenge", title=topics.topic_1)
            await asyncio.sleep(5)
            
        # 2. Deep Dive Subject 1
        if topics.topic_2:
            content = await self.agent.get_deep_dive(topics.topic_2)
            await self.sender.send_to_all(content, title=f"Deep Dive: {topics.topic_2}")
            await asyncio.sleep(5)
            
        # 3. Deep Dive Subject 2
        if topics.topic_3:
            content = await self.agent.get_deep_dive(topics.topic_3)
            await self.sender.send_to_all(content, title=f"Deep Dive: {topics.topic_3}")
            await asyncio.sleep(5)
            
        # 4. Fresh Updates 1
        if topics.topic_4:
            content = await self.agent.get_curated_content("Tech_news", f"Top global news about {topics.topic_4} for today.")
            await self.sender.send_to_all(content, title=f"Fresh Updates: {topics.topic_4}")
            await asyncio.sleep(5)
            
        # 5. Fresh Updates 2
        if topics.topic_5:
            content = await self.agent.get_curated_content("Global_news", f"Top global news about {topics.topic_5} for today.")
            await self.sender.send_to_all(content, title=f"Fresh Updates: {topics.topic_5}")
            
        logger.info(f"✅ [{self.phone_number}] Content delivery cycle completed.")

    async def start(self):
        await self.whatsapp.connect()
        # Optionally register incoming message handlers here
        self.whatsapp.register_incoming_handler()

        self.config = ConfigManager.load_config(self.phone_number)
        self.schedule_time = self.config.schedule_time
        hour, minute = map(int, self.schedule_time.split(":"))

        self.scheduler.add_job(
            self.daily_task,
            trigger="cron",
            hour=hour,
            minute=minute,
        )

        self.scheduler.start()
        logger.info(f"✅ [{self.phone_number}] Scheduler started — daily delivery at {self.schedule_time}")
