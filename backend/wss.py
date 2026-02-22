import asyncio
import inspect
import threading
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
import ip

class Server:
    def __init__(self, host="10.48.83.217", port=8765):
        self.host = ip.get_local_ip_robust() or host
        self.port = port
        self.callbacks = []
        self.connected_clients = set()

    async def _send_client(self, ws, payload: bytes):
        """Send to a single client and prune dead connections."""
        try:
            await ws.send(payload)
        except ConnectionClosed:
            self.connected_clients.discard(ws)

    def broadcast(self, payload: bytes | bytearray | str):
        """Send a message to every client.

        - Coerce bytearray → bytes so the browser gets a binary frame with the
          expected length (avoids empty Blob on the frontend).
        - Fire-and-forget using create_task so callers can stay sync.
        """

        # Normalise the payload type for websockets
        if isinstance(payload, bytearray):
            payload = bytes(payload)

        for ws in list(self.connected_clients):
            asyncio.create_task(self._send_client(ws, payload))

    def onMessage(self, callback):
        # callback can be sync or async; we'll handle both
        self.callbacks.append(callback)

    async def _dispatch(self, message, websocket):
        for cb in list(self.callbacks):
            try:
                if inspect.iscoroutinefunction(cb):
                    # thread it
                    threading.Thread(target=asyncio.run, args=(cb(message, websocket),)).start()
                else:
                    cb(message, websocket)
            except Exception as e:
                print(f"Callback error: {e!r}")

    # NOTE: path is optional so this handler works with older AND newer websockets APIs
    async def echo(self, websocket, path=None):
        self.connected_clients.add(websocket)
        #print(f"Client connected: {websocket.remote_address}")
        try:
            async for message in websocket:
                await self._dispatch(message, websocket)
        except ConnectionClosed:
            pass
        finally:
            self.connected_clients.discard(websocket)

    async def start(self):
        async with serve(self.echo, self.host, self.port, ping_interval=15,   # send ping more often (helps NAT / Wi-Fi idle timeouts)
            ping_timeout=30) as server:
            print(f"Server started at ws://{self.host}:{self.port}")
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(Server().start())