import os
import asyncio
from neonize.aioze.client import NewAClient
from neonize.utils.jid import build_jid
from neonize.events import ConnectedEv, MessageEv, DisconnectedEv, LoggedOutEv
import segno
from app.database.db import get_conn
from app.core.logging import get_logger
from app.core.utils import ContextAdapter
from app.core.limiter import TokenBucketLimiter

from app.core.config import settings

logger = get_logger("WhatsAppClient")

# WhatsApp Outgoing Limiter: 1 msg/sec with burst of 3
sender_limiter = TokenBucketLimiter(rate=1.0, capacity=3)

class WhatsAppClient:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number.strip().lstrip("+")
        self.logger = ContextAdapter(logger, {"phone": self.phone_number})
        
        from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
        db_url = settings.get_database_url()
        # Neonize (whatsmeow) generally expects 'postgres://' for PostgreSQL
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgres://", 1)
            
        # Add sslmode=disable to prevent 'SSL is not enabled on the server' panic
        if "?" in db_url:
            db_url += "&sslmode=disable"
        else:
            db_url += "?sslmode=disable"
            
        self.client = NewAClient(
            name=db_url,
            uuid=self.phone_number,
            props=DeviceProps(os="Mac OS")
        )
        self.connected = False
        self.is_ready = asyncio.Event()
        self.qr_generated = False
        self.register_internal_handlers()
        
        # Setup intercept for QR code and render it as a PNG image
        async def on_qr(client_instance, data_qr: bytes):
            qr_file = os.path.join("data", f"qr_{self.phone_number}.png")
            # Render the QR data into a valid PNG file
            segno.make(data_qr).save(qr_file, scale=10)
            self.qr_generated = True
            self.logger.info(f"✅ [{self.phone_number}] QR Code image rendered and saved to {qr_file}. Please scan in WhatsApp.")
            
        if hasattr(self.client.event, 'qr'):
            self.client.event.qr(on_qr)
        elif hasattr(self.client, 'qr'):
            self.client.qr(on_qr)

    def register_internal_handlers(self):
        """Register handlers for connection lifecycle."""
        @self.client.event(ConnectedEv)
        async def on_connected(client: NewAClient, event: ConnectedEv):
            # Identity Guard: Ensure this event belongs to THIS instance
            if client is not self.client:
                return

            self.logger.info(f"✨ [{self.phone_number}] Connected successfully!")
            self.is_ready.set()
            self.connected = True
            
            # Remove QR file if it exists after pairing
            qr_file = os.path.join("data", f"qr_{self.phone_number}.png")
            if os.path.exists(qr_file):
                try:
                    os.remove(qr_file)
                except Exception:
                    pass
            
            # Update DB status
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO user_status(phone_number, is_paired, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                    "ON CONFLICT (phone_number) DO UPDATE SET is_paired = TRUE, updated_at = CURRENT_TIMESTAMP",
                    (self.phone_number, True)
                )

        @self.client.event(DisconnectedEv)
        async def on_disconnected(client: NewAClient, event: DisconnectedEv):
            if client is not self.client:
                return
            self.logger.warning(f"⚠️ [{self.phone_number}] WhatsApp disconnected.")
            self.connected = False
            self.is_ready.clear()

        @self.client.event(LoggedOutEv)
        async def on_logged_out(client: NewAClient, event: LoggedOutEv):
            if client is not self.client:
                return
            self.logger.error(f"❌ [{self.phone_number}] WhatsApp logged out. QR pairing required.")
            self.connected = False
            self.is_ready.clear()
            
            with get_conn() as conn:
                conn.execute("UPDATE user_status SET is_paired = FALSE WHERE phone_number = %s", (self.phone_number,))

    async def connect(self, retries: int = 3, timeout: int = 90):
        """Standard connect for NewAClient with robust retry."""
        if self.connected and self.is_ready.is_set():
            return
            
        for attempt in range(retries):
            self.logger.info(f"[{self.phone_number}] connection attempt {attempt+1}/{retries}")
            self.is_ready.clear()
            self.connected = False
            
            connect_task = asyncio.create_task(self.client.connect())
            
            try:
                await asyncio.wait_for(self.is_ready.wait(), timeout=timeout)
                self.logger.info(f"✅ [{self.phone_number}] WhatsApp ready.")
                return
            except asyncio.TimeoutError:
                self.logger.error(f"❌ [{self.phone_number}] Connection timeout.")
                connect_task.cancel()
                await asyncio.sleep(5)
                
        self.connected = False
        raise ConnectionError(f"Failed to connect +{self.phone_number}")

    async def ensure_connected(self):
        if not (self.connected and self.is_ready.is_set()):
            await self.connect()

    async def send_message(self, text: str, retries: int = 3):
        await self.ensure_connected()
        await sender_limiter.consume(wait=True)
        jid = build_jid(self.phone_number)
        
        for attempt in range(retries):
            try:
                await self.client.send_message(jid, text)
                self.logger.debug(f"✅ [{self.phone_number}] Message sent.")
                return
            except Exception as e:
                self.logger.error(f"Send error (Attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    raise e

    async def send_image(self, image_path: str, caption: str = None, retries: int = 3):
        await self.ensure_connected()
        await sender_limiter.consume(wait=True)
        jid = build_jid(self.phone_number)

        if not os.path.exists(image_path):
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        for attempt in range(retries):
            try:
                await self.client.send_image(jid, image_bytes, caption=caption)
                return
            except Exception as e:
                if attempt == retries - 1: raise e
                await asyncio.sleep(2 * (attempt + 1))

    def register_incoming_handler(self, handler=None):
        """Register callback for incoming messages with strict account filtering."""
        @self.client.event(MessageEv)
        async def on_message(client: NewAClient, message: MessageEv):
            # Identity Guard: Only process messages meant for THIS client instance
            if client is not self.client:
                return
            
            if handler:
                await handler(client, message)
            else:
                self.logger.info(f"📩 [{self.phone_number}] Incoming message received.")
