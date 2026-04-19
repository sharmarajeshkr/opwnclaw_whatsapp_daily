import os
import asyncio
from neonize.aioze.client import NewAClient
from neonize.utils.jid import build_jid
from neonize.events import ConnectedEv, MessageEv, DisconnectedEv, LoggedOutEv
import segno
from src.core.db import get_conn
from src.core.logger import get_logger
from src.core.logging_utils import ContextAdapter

logger = get_logger("WhatsAppClient")

class WhatsAppClient:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number.strip().lstrip("+")
        self.logger = ContextAdapter(logger, {"phone": self.phone_number})
        
        # Ensure users directory exists
        users_dir = os.path.join("data", "users")
        os.makedirs(users_dir, exist_ok=True)
        
        session_path = os.path.join(users_dir, f"{self.phone_number}.sqlite3")
        from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
        self.client = NewAClient(
            session_path, 
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
            self.logger.info(f"✨ [{self.phone_number}] Connected successfully!")
            self.is_ready.set()
            self.connected = True
            
            # Remove QR file if it exists after pairing
            qr_file = os.path.join("data", f"qr_{self.phone_number}.png")
            if os.path.exists(qr_file):
                try:
                    os.remove(qr_file)
                    self.logger.debug(f"Deleted QR file {qr_file} after successful pairing.")
                except Exception as e:
                    self.logger.warning(f"Could not delete QR file {qr_file}: {e}")
            
            # Update DB status
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO user_status(phone_number, is_paired, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                    "ON CONFLICT (phone_number) DO UPDATE SET is_paired = TRUE, updated_at = CURRENT_TIMESTAMP",
                    (self.phone_number, True)
                )

        @self.client.event(DisconnectedEv)
        async def on_disconnected(client: NewAClient, event: DisconnectedEv):
            self.logger.warning(f"⚠️ [{self.phone_number}] WhatsApp disconnected. Connection lost.")
            self.connected = False
            self.is_ready.clear()

        @self.client.event(LoggedOutEv)
        async def on_logged_out(client: NewAClient, event: LoggedOutEv):
            self.logger.error(f"❌ [{self.phone_number}] WhatsApp logged out. QR pairing required again.")
            self.connected = False
            self.is_ready.clear()
            
            # Update DB status
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO user_status(phone_number, is_paired, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                    "ON CONFLICT (phone_number) DO UPDATE SET is_paired = FALSE, updated_at = CURRENT_TIMESTAMP",
                    (self.phone_number, False)
                )

    async def connect(self, retries: int = 3, timeout: int = 90):
        """Standard connect for NewAClient with robust retry."""
        if self.connected and self.is_ready.is_set():
            return
            
        for attempt in range(retries):
            self.logger.info(f"[{self.phone_number}] Initiating WhatsApp connection (Attempt {attempt+1}/{retries})...")
            self.is_ready.clear()
            self.connected = False
            
            # Start the connection task
            connect_task = asyncio.create_task(self.client.connect())
            
            # Wait for the ConnectedEv or timeout
            try:
                self.logger.debug(f"[{self.phone_number}] Waiting for connection signal...")
                await asyncio.wait_for(self.is_ready.wait(), timeout=timeout)
                self.logger.info(f"✅ [{self.phone_number}] WhatsApp connection ready.")
                return
            except asyncio.TimeoutError:
                self.logger.error(f"❌ [{self.phone_number}] Timeout waiting for WhatsApp connection.")
                connect_task.cancel()
                await asyncio.sleep(5)
                
        # If we exhausted all retries
        self.connected = False
        raise ConnectionError(f"Failed to connect WhatsApp client for +{self.phone_number} after {retries} attempts.")

    async def ensure_connected(self):
        """Check connection state and auto-reconnect if needed before action."""
        if self.connected and self.is_ready.is_set():
            return
        await self.connect()

    async def send_message(self, text: str, retries: int = 3):
        await self.ensure_connected()
        jid = build_jid(self.phone_number)
        
        for attempt in range(retries):
            try:
                await self.client.send_message(jid, text)
                self.logger.debug(f"✅ [{self.phone_number}] Message sent to {jid} (Attempt {attempt+1})")
                return
            except Exception as e:
                self.logger.error(f"Error sending message (Attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    raise e

    async def send_image(self, image_path: str, caption: str = None, retries: int = 3):
        await self.ensure_connected()
        jid = build_jid(self.phone_number)

        if not os.path.exists(image_path):
            self.logger.error(f"Image not found at {image_path}")
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        for attempt in range(retries):
            try:
                await self.client.send_image(jid, image_bytes, caption=caption)
                self.logger.debug(f"✅ [{self.phone_number}] Image sent successfully (Attempt {attempt+1})")
                return
            except Exception as e:
                self.logger.error(f"Error sending image (Attempt {attempt+1}): {e}")
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
                 self.logger.info(f"📩 [{self.phone_number}] Incoming message: {message}")
