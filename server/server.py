import os
import asyncio
import websockets
import json
import uuid
from datetime import datetime
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

clients = set()

ids = {}      
by_id = {}    
names = {}    
by_name = {}  

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

async def safe_send(ws, message):
    try:
        await ws.send(message)
    except (ConnectionClosedOK, ConnectionClosedError, RuntimeError):
        pass

async def broadcast(message: str):
    if not clients:
        return
    await asyncio.gather(*(safe_send(ws, message) for ws in list(clients)), return_exceptions=True)

async def handler(websocket, path=None):
    # assigning a server-side id right here 
    client_id = str(uuid.uuid4())
    clients.add(websocket)
    ids[websocket] = client_id
    by_id[client_id] = websocket
    names[websocket] = None

    # "this is me"
    await safe_send(websocket, json.dumps({
        "type": "connected",
        "client_id": client_id,
        "time": now_iso()
    }))

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except:
                data = {"type": "message", "message": raw}

            typ = data.get("type", "message")

            if typ == "join":
                requested = (data.get("name") or "").strip()
                if not requested:
                    stored_name = f"User-{client_id[:6]}"
                else:
                    base = requested
                    stored_name = base
                    i = 1
                    while stored_name in by_name:
                        stored_name = f"{base}{i}"
                        i += 1

                names[websocket] = stored_name
                by_name[stored_name] = websocket

                await safe_send(websocket, json.dumps({
                    "type": "ack",
                    "action": "join",
                    "status": "ok",
                    "client_id": client_id,
                    "name": stored_name,
                    "online": list(by_name.keys()),
                    "time": now_iso()
                }))

                await broadcast(json.dumps({
                    "type": "status",
                    "message": f"{stored_name} joined the chat",
                    "time": now_iso()
                }))
                continue

            if typ == "list":
                await safe_send(websocket, json.dumps({
                    "type": "list",
                    "online": list(by_name.keys()),
                    "time": now_iso()
                }))
                continue

            if typ == "message":
                sender_id = ids.get(websocket)
                sender_name = names.get(websocket) or f"User-{sender_id[:6]}"
                msg_text = data.get("message", "")

                payload = {
                    "type": "message",
                    "from_id": sender_id,
                    "from_name": sender_name,
                    "message": msg_text,
                    "time": now_iso(),
                    "private": False
                }

                await broadcast(json.dumps(payload))
                continue

            await safe_send(websocket, json.dumps({
                "type": "error",
                "message": f"unknown message type: {typ}",
                "time": now_iso()
            }))

    except (ConnectionClosedOK, ConnectionClosedError):
        pass
    finally:
        if websocket in clients:
            clients.remove(websocket)

        client_id = ids.pop(websocket, None)
        if client_id:
            by_id.pop(client_id, None)

        name = names.pop(websocket, None)
        if name:
            by_name.pop(name, None)
            await broadcast(json.dumps({
                "type": "status",
                "message": f"{name} left the chat",
                "time": now_iso()
            }))
        else:
            await broadcast(json.dumps({
                "type": "status",
                "message": f"User-{(client_id or '')[:6]} disconnected",
                "time": now_iso()
            }))

async def main():
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "6789"))

    async with websockets.serve(
        handler, host, port,
        ping_interval=20, ping_timeout=20
    ):
        print(f"WebSocket server listening on ws://{host}:{port}")
        await asyncio.Future()  

if __name__ == "__main__":
    asyncio.run(main())
