"""Simple WebSocket client for testing FastAPI incident broadcasts."""

import asyncio
import websockets


WS_URL = "ws://localhost:5000/ws/incidents"


async def main() -> None:
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as websocket:
        print("Connected to incident WebSocket. Listening for messages...")

        while True:
            message = await websocket.recv()
            print(f"Received: {message}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("WebSocket test client stopped.")
