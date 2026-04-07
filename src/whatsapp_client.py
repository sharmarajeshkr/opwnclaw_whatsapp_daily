import os
import asyncio
import time
from dotenv import load_dotenv
from neonize.aioze.client import NewAClient
from neonize.utils.jid import build_jid
from neonize.events import ConnectedEv, MessageEv
from src.logger_config import get_logger
logger = get_logger(os.path.basename(__file__) if "__file__" in locals() else "OpenClawBot")


load_dotenv()


class WhatsAppClient:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number.strip().lstrip("+")
        
        # Ensure users directory exists
        users_dir = os.path.join("data", "users")
        os.makedirs(users_dir, exist_ok=True)
        
        session_path = os.path.join(users_dir, f"{self.phone_number}.sqlite3")
        self.client = NewAClient(session_path)
        self.connected = False
        self.is_ready = asyncio.Event()
        self.register_internal_handlers()
        
        # Intercept QR code and save it
        def on_qr(client_instance, data_qr: bytes):
            qr_file = os.path.join("data", f"qr_{self.phone_number}.png")
            with open(qr_file, "wb") as f:
                f.write(data_qr)
            logger.info(f"QR Code generated and saved to {qr_file}")
            
        if hasattr(self.client.event, 'qr'):
            self.client.event.qr(on_qr)
        elif hasattr(self.client, 'qr'):
            self.client.qr(on_qr)

    def register_internal_handlers(self):
        """Register handlers for connection lifecycle."""
        @self.client.event(ConnectedEv)
        async def on_connected(client: NewAClient, event: ConnectedEv):
            logger.debug("DEBUG: Received ConnectedEv from WhatsApp")
            self.is_ready.set()
            self.connected = True

    async def connect(self):
        """Standard connect for NewAClient."""
        if self.connected and self.is_ready.is_set():
            return
            
        logger.debug("DEBUG: Starting WhatsApp connection...")
        self.is_ready.clear()
        
        # Start the connection task
        asyncio.create_task(self.client.connect())
        
        # Wait for the ConnectedEv or timeout
        try:
            logger.debug("DEBUG: Waiting for ConnectedEv signal...")
            await asyncio.wait_for(self.is_ready.wait(), timeout=60)
            logger.info("✅ WhatsApp fully ready and synchronized")
        except asyncio.TimeoutError:
            logger.error("ERROR: Timeout waiting for WhatsApp connection signal")
            self.connected = False

    async def ensure_connected(self):
        if self.connected:
            return
        await self.connect()

    async def send_message(self, text: str, retries: int = 3):
        await self.ensure_connected()

        if not self.phone_number:
            raise ValueError("phone_number missing for this client")

        # Use build_jid directly with the number string; neonize handles the server suffix internally.
        jid = build_jid(self.phone_number)
        
        for attempt in range(retries):
            try:
                logger.debug(f"DEBUG: Sending to {jid} (Attempt {attempt+1}/{retries})")
                await self.client.send_message(jid, text)
                logger.info("✅ Message sent successfully")
                return
            except Exception as e:
                logger.error(f"ERROR: Failed to send message (Attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    logger.info("❌ Final attempt failed. Message aborted.")
                    raise e

    async def send_image(self, image_path: str, caption: str = None, retries: int = 3):
        await self.ensure_connected()

        if not self.phone_number:
            raise ValueError("phone_number missing for this client")

        # Use build_jid directly with the number string; neonize handles the server suffix internally.
        jid = build_jid(self.phone_number)

        if not os.path.exists(image_path):
            logger.error(f"ERROR: Image file not found at {image_path}")
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        for attempt in range(retries):
            try:
                logger.debug(f"DEBUG: Sending image to {jid} (Attempt {attempt+1}/{retries})")
                await self.client.send_image(jid, image_bytes, caption=caption)
                logger.info("✅ Image sent successfully")
                return
            except Exception as e:
                logger.error(f"ERROR: Failed to send image (Attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    raise e

    def register_incoming_handler(self):
        """Register callback for incoming replies."""

        @self.client.event(MessageEv)
        async def on_message(client: NewAClient, message: MessageEv):
            logger.info("📩 Incoming WhatsApp message received")
            logger.info(message)