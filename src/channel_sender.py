import asyncio
import os
import httpx
from src.config_manager import ConfigManager
from src.logger_config import get_logger
logger = get_logger(os.path.basename(__file__) if "__file__" in locals() else "OpenClawBot")


class ChannelSender:
    def __init__(self, whatsapp_client):
        self.whatsapp_client = whatsapp_client
        self.config = ConfigManager.load_config()

    def refresh_config(self):
        self.config = ConfigManager.load_config()

    async def send_to_all(self, text: str, image_path: str = None, caption: str = None, title: str = ""):
        """Sends the provided content to all active configurable channels."""
        self.refresh_config()
        channels = self.config.get("channels", {})
        
        tasks = []
        
        formatted_text = f"*{title}*\n\n{text}" if title else text

        # WhatsApp
        if channels.get("whatsapp_target"):
            # Override target if updated from config
            self.whatsapp_client.phone_number = channels["whatsapp_target"]
            tasks.append(self._send_whatsapp(formatted_text, image_path, caption))
            
        # Telegram
        tg_token = channels.get("telegram_bot_token")
        tg_chat = channels.get("telegram_chat_id")
        if tg_token and tg_chat:
            tasks.append(self._send_telegram(tg_token, tg_chat, formatted_text, image_path, caption))
            
        # Slack
        slack_webhook = channels.get("slack_webhook_url")
        if slack_webhook:
            tasks.append(self._send_slack(slack_webhook, formatted_text))
            
        if tasks:
            await asyncio.gather(*tasks)
            
    async def _send_whatsapp(self, text: str, image_path: str, caption: str):
        try:
            await self.whatsapp_client.send_message(text)
            if image_path and os.path.exists(image_path):
                await asyncio.sleep(2)
                await self.whatsapp_client.send_image(image_path, caption=caption or "")
        except Exception as e:
            logger.info(f"WhatsApp Deployment Error: {e}")

    async def _send_telegram(self, token: str, chat_id: str, text: str, image_path: str, caption: str):
        try:
            async with httpx.AsyncClient() as client:
                if image_path and os.path.exists(image_path):
                    url = f"https://api.telegram.org/bot{token}/sendPhoto"
                    with open(image_path, "rb") as photo:
                        await client.post(url, data={"chat_id": chat_id, "caption": caption or ""}, files={"photo": photo})
                        await asyncio.sleep(1)
                
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                # Chunk to avoid telegram limit
                for i in range(0, len(text), 4000):
                    chunk = text[i:i+4000]
                    await client.post(url, json={"chat_id": chat_id, "text": chunk})
        except Exception as e:
            logger.info(f"Telegram Deployment Error: {e}")

    async def _send_slack(self, webhook_url: str, text: str):
        try:
            async with httpx.AsyncClient() as client:
                payload = {"text": text}
                await client.post(webhook_url, json=payload)
        except Exception as e:
            logger.info(f"Slack Deployment Error: {e}")
