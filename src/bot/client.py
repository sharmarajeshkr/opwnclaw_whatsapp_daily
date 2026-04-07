import os
import asyncio
from neonize.aioze.client import NewAClient
from neonize.utils.jid import build_jid
from neonize.events import ConnectedEv, MessageEv
from src.core.logger import get_logger

logger = get_logger("WhatsAppClient")

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
        
        # Setup intercept for QR code and save it to data directory
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
            logger.debug(f"[{self.phone_number}] ConnectedEv event received.")
            self.is_ready.set()
            self.connected = True

    async def connect(self):
        """Standard connect for NewAClient."""
        if self.connected and self.is_ready.is_set():
            return
            
        logger.info(f"[{self.phone_number}] Initiating WhatsApp connection...")
        self.is_ready.clear()
        
        # Start the connection task
        asyncio.create_task(self.client.connect())
        
        # Wait for the ConnectedEv or timeout
        try:
            logger.debug(f"[{self.phone_number}] Waiting for connection signal...")
            await asyncio.wait_for(self.is_ready.wait(), timeout=60)
            logger.info(f"✅ [{self.phone_number}] WhatsApp connection ready.")
        except asyncio.TimeoutError:
            logger.error(f"❌ [{self.phone_number}] Timeout waiting for WhatsApp connection.")
            self.connected = False

    async def ensure_connected(self):
        if self.connected:
            return
        await self.connect()

    async def send_message(self, text: str, retries: int = 3):
        await self.ensure_connected()
        jid = build_jid(self.phone_number)
        
        for attempt in range(retries):
            try:
                await self.client.send_message(jid, text)
                logger.debug(f"✅ [{self.phone_number}] Message sent to {jid} (Attempt {attempt+1})")
                return
            except Exception as e:
                logger.error(f"Error sending message (Attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    raise e

    async def send_image(self, image_path: str, caption: str = None, retries: int = 3):
        await self.ensure_connected()
        jid = build_jid(self.phone_number)

        if not os.path.exists(image_path):
            logger.error(f"Image not found at {image_path}")
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        for attempt in range(retries):
            try:
                await self.client.send_image(jid, image_bytes, caption=caption)
                logger.debug(f"✅ [{self.phone_number}] Image sent successfully (Attempt {attempt+1})")
                return
            except Exception as e:
                logger.error(f"Error sending image (Attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    raise e

    def register_incoming_handler(self, handler=None):
        """Register callback for incoming messages."""
        if handler:
             @self.client.event(MessageEv)
             async def on_message(client: NewAClient, message: MessageEv):
                 await handler(client, message)
        else:
             @self.client.event(MessageEv)
             async def on_message(client: NewAClient, message: MessageEv):
                 logger.info(f"📩 [{self.phone_number}] Incoming message: {message}")
