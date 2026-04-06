import os
import asyncio
from dotenv import load_dotenv
from neonize.aioze.client import NewAClient
from neonize.utils.jid import build_jid

load_dotenv()


class WhatsAppClient:
    def __init__(self, session_name: str = "interview_bot"):
        self.phone_number = os.getenv("WHATSAPP_TARGET_NUMBER")
        self.client = NewAClient(f"{session_name}.sqlite3")
        self.connected = False

    async def connect(self):
        """Standard connect for NewAClient."""
        if self.connected:
            return
        print("DEBUG: Starting WhatsApp connection...", flush=True)
        await self.client.connect()
        self.connected = True
        print("✅ WhatsApp connected", flush=True)

    async def ensure_connected(self):
        if self.connected:
            return
        await self.connect()

    async def send_message(self, text: str):
        await self.ensure_connected()

        if not self.phone_number:
            raise ValueError("WHATSAPP_TARGET_NUMBER missing in .env")

        # Use build_jid directly with the number string; neonize handles the server suffix internally.
        phone = self.phone_number.strip("+")
        jid = build_jid(phone)
        print(f"DEBUG: Sending to {jid}", flush=True)

        await self.client.send_message(
            jid,
            text,
        )
        print("✅ Message sent successfully", flush=True)

    async def send_image(self, image_path: str, caption: str = None):
        await self.ensure_connected()

        if not self.phone_number:
            raise ValueError("WHATSAPP_TARGET_NUMBER missing in .env")

        # Use build_jid directly with the number string; neonize handles the server suffix internally.
        phone = self.phone_number.strip("+")
        jid = build_jid(phone)
        print(f"DEBUG: Sending image to {jid} (Path: {image_path})", flush=True)

        if not os.path.exists(image_path):
            print(f"ERROR: Image file not found at {image_path}")
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        await self.client.send_image(
            jid,
            image_bytes,
            caption=caption
        )
        print("✅ Image sent successfully", flush=True)

    def register_incoming_handler(self):
        """Register callback for incoming replies."""

        @self.client.event("message")
        def on_message(message):
            print("📩 Incoming WhatsApp message received")
            print(message)