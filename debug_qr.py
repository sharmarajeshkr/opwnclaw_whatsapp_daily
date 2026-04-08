import asyncio
import os
import sys
from neonize.aioze.client import NewAClient
from neonize.events import ConnectedEv
import segno

async def debug_qr(phone: str):
    session_path = os.path.join("data", "users", f"{phone}.sqlite3")
    client = NewAClient(session_path)
    
    @client.event(ConnectedEv)
    async def on_connected(client, event):
        print(f"DEBUG: Connected!")

    def on_qr(client_instance, data_qr: bytes):
        print(f"DEBUG: QR RECEIVED! Size: {len(data_qr)}")
        qr_file = f"debug_qr_{phone}.png"
        segno.make(data_qr).save(qr_file, scale=10)
        print(f"DEBUG: QR SAVED TO {qr_file}")

    if hasattr(client.event, 'qr'):
        client.event.qr(on_qr)
        print("DEBUG: Registered via client.event.qr")
    elif hasattr(client, 'qr'):
        client.qr(on_qr)
        print("DEBUG: Registered via client.qr")
    else:
        print("DEBUG: FAILED TO FIND QR EVENT HANDLER in client")

    print(f"DEBUG: Connecting...")
    await client.connect()

if __name__ == "__main__":
    phone = sys.argv[1] if len(sys.argv) > 1 else "test"
    asyncio.run(debug_qr(phone))
