import os
import asyncio
import time
from dotenv import load_dotenv
from neonize.aioze.client import NewAClient
from neonize.utils.jid import build_jid
from neonize.events import ConnectedEv, MessageEv

load_dotenv()


class WhatsAppClient:
    def __init__(self, session_name: str = "interview_bot"):
        self.phone_number = os.getenv("WHATSAPP_TARGET_NUMBER")
        self.client = NewAClient(f"{session_name}.sqlite3")
        self.connected = False
        self.is_ready = asyncio.Event()
        self.register_internal_handlers()

    def register_internal_handlers(self):
        """Register handlers for connection lifecycle."""
        @self.client.event(ConnectedEv)
        async def on_connected(client: NewAClient, event: ConnectedEv):
            print("DEBUG: Received ConnectedEv from WhatsApp", flush=True)
            self.is_ready.set()
            self.connected = True

    async def connect(self):
        """Standard connect for NewAClient."""
        if self.connected and self.is_ready.is_set():
            return
            
        print("DEBUG: Starting WhatsApp connection...", flush=True)
        self.is_ready.clear()
        
        # Start the connection task
        asyncio.create_task(self.client.connect())
        
        # Wait for the ConnectedEv or timeout
        try:
            print("DEBUG: Waiting for ConnectedEv signal...", flush=True)
            await asyncio.wait_for(self.is_ready.wait(), timeout=60)
            print("✅ WhatsApp fully ready and synchronized", flush=True)
        except asyncio.TimeoutError:
            print("ERROR: Timeout waiting for WhatsApp connection signal")
            self.connected = False

    async def ensure_connected(self):
        if self.connected:
            return
        await self.connect()

    async def send_message(self, text: str, retries: int = 3):
        await self.ensure_connected()

        if not self.phone_number:
            raise ValueError("WHATSAPP_TARGET_NUMBER missing in .env")

        # Use build_jid directly with the number string; neonize handles the server suffix internally.
        phone = self.phone_number.strip("+")
        jid = build_jid(phone)
        
        for attempt in range(retries):
            try:
                print(f"DEBUG: Sending to {jid} (Attempt {attempt+1}/{retries})", flush=True)
                await self.client.send_message(jid, text)
                print("✅ Message sent successfully", flush=True)
                return
            except Exception as e:
                print(f"ERROR: Failed to send message (Attempt {attempt+1}): {e}", flush=True)
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    print("❌ Final attempt failed. Message aborted.", flush=True)
                    raise e

    async def send_image(self, image_path: str, caption: str = None, retries: int = 3):
        await self.ensure_connected()

        if not self.phone_number:
            raise ValueError("WHATSAPP_TARGET_NUMBER missing in .env")

        # Use build_jid directly with the number string; neonize handles the server suffix internally.
        phone = self.phone_number.strip("+")
        jid = build_jid(phone)

        if not os.path.exists(image_path):
            print(f"ERROR: Image file not found at {image_path}")
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        for attempt in range(retries):
            try:
                print(f"DEBUG: Sending image to {jid} (Attempt {attempt+1}/{retries})", flush=True)
                await self.client.send_image(jid, image_bytes, caption=caption)
                print("✅ Image sent successfully", flush=True)
                return
            except Exception as e:
                print(f"ERROR: Failed to send image (Attempt {attempt+1}): {e}", flush=True)
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    raise e

    def register_incoming_handler(self):
        """Register callback for incoming replies."""

        @self.client.event(MessageEv)
        async def on_message(client: NewAClient, message: MessageEv):
            print("📩 Incoming WhatsApp message received")
            print(message)