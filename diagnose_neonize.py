import asyncio
from neonize.aioze.client import NewAClient

async def check():
    client = NewAClient("test.sqlite3")
    print(f"Type of client.connect: {type(client.connect)}")
    conn = client.connect()
    print(f"Type of client.connect(): {type(conn)}")
    if asyncio.iscoroutine(conn):
        print("client.connect() is a coroutine.")
    else:
        print("client.connect() is NOT a coroutine.")

if __name__ == "__main__":
    asyncio.run(check())
