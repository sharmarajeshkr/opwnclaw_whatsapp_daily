import os
import asyncio
from neonize.aioze.client import NewAClient
from neonize.utils.jid import build_jid
from dotenv import load_dotenv

load_dotenv()

async def main():
    session = os.getenv("WHATSAPP_SESSION_NAME", "interview_bot_v5")
    phone = os.getenv("WHATSAPP_TARGET_NUMBER").strip('+')
    
    print(f"Testing delivery to {phone} using session {session}...")
    client = NewAClient(f"{session}.sqlite3")
    
    # Start connection
    await client.connect()
    
    # Wait for authentication/sync
    print("Waiting 15 seconds for sync...")
    await asyncio.sleep(15)
    
    target = build_jid(f"{phone}@s.whatsapp.net")
    print(f"Sending 'Hi' to {target}...")
    
    try:
        # Use a short timeout for the test
        await asyncio.wait_for(client.send_message(target, "Hi! This is a simple test message."), timeout=30.0)
        print("SUCCESS: 'Hi' message sent!")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
