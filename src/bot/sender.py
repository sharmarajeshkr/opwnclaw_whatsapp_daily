import asyncio
import os
import httpx
from src.core.config import ConfigManager
from src.core.logger import get_logger

logger = get_logger("ChannelSender")

class ChannelSender:
    def __init__(self, whatsapp_client, phone_number: str):
        self.whatsapp_client = whatsapp_client
        self.phone_number = phone_number
        self.config = ConfigManager.load_config(phone_number)

    def refresh_config(self):
        self.config = ConfigManager.load_config(self.phone_number)

    async def send_to_all(self, text: str, image_path: str = None, caption: str = None, title: str = ""):
        """Sends the provided content to all active configurable channels."""
        self.refresh_config()
        channels = self.config.channels
        
        tasks = []
        formatted_text = f"*{title}*\n\n{text}" if title else text

        # WhatsApp
        if channels.whatsapp_target:
            tasks.append(self._send_whatsapp(formatted_text, image_path, caption))
            
        # Telegram
        if channels.telegram_bot_token and channels.telegram_chat_id:
            tasks.append(self._send_telegram(channels.telegram_bot_token, channels.telegram_chat_id, formatted_text, image_path, caption))
            
        # Slack
        if channels.slack_webhook_url:
            tasks.append(self._send_slack(channels.slack_webhook_url, formatted_text))
            
        if tasks:
            await asyncio.gather(*tasks)
            
    async def _send_whatsapp(self, text: str, image_path: str, caption: str):
        try:
            await self.whatsapp_client.send_message(text)
            if image_path and os.path.exists(image_path):
                await asyncio.sleep(2)
                await self.whatsapp_client.send_image(image_path, caption=caption or "")
        except Exception as e:
            logger.error(f"WhatsApp Deployment Error for +{self.phone_number}: {e}")

    async def _send_telegram(self, token: str, chat_id: str, text: str, image_path: str, caption: str):
        try:
            async with httpx.AsyncClient() as client:
                if image_path and os.path.exists(image_path):
                    url = f"https://api.telegram.org/bot{token}/sendPhoto"
                    with open(image_path, "rb") as photo:
                        await client.post(url, data={"chat_id": chat_id, "caption": caption or ""}, files={"photo": photo})
                        await asyncio.sleep(1)
                
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                for i in range(0, len(text), 4000):
                    chunk = text[i:i+4000]
                    await client.post(url, json={"chat_id": chat_id, "text": chunk})
        except Exception as e:
            logger.error(f"Telegram Deployment Error for +{self.phone_number}: {e}")

    async def _send_slack(self, webhook_url: str, text: str):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json={"text": text})
        except Exception as e:
            logger.error(f"Slack Deployment Error for +{self.phone_number}: {e}")
