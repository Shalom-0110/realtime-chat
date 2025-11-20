# server.py
import asyncio
import websockets
import json
from datetime import datetime

clients = set()

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

async def broadcast(message: str):
    # Send message to all connected clients.
    if not clients:
        return
    await asyncio.gather(*(ws.send(message) for ws in clients), return_exceptions=True)

async def handler(websocket, path):
    clients.add(websocket)
    try:
        join = {"type": "status", "message": "A user joined", "time": now_iso()}
        await broadcast(json.dumps(join))

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except:
                data = {"type": "message", "name": "Anon", "message": raw}

            data["time"] = now_iso()

            await broadcast(json.dumps(data))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.remove(websocket)
        leave = {"type": "status", "message": "A user left", "time": now_iso()}
        await broadcast(json.dumps(leave))

if __name__ == "__main__":
    start_server = websockets.serve(
        handler, "localhost", 6789,
        ping_interval=20, 
        ping_timeout=20
    )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server)
    print("WebSocket server listening on ws://localhost:6789")
    loop.run_forever()
