import asyncio
import json
import websockets

WS_URL = "ws://localhost:5000/ws/incidents"

async def main():
    try:
        async with websockets.connect(WS_URL, ping_interval=None) as websocket:
            print("Connected to live feed")
            while True:
                message = await websocket.recv()
                try:
                    data = json.loads(message)
                    print(json.dumps(data, indent=2))
                except Exception:
                    print("Message:", message)
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(main())


