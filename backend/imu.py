import asyncio
import inspect

import serial
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
import struct


class IMU:
    def __init__(self, host, port=9967, reconnect_delay: float = 2.0):
        self.host = host
        self.port = port
        self.url = f"ws://{host}:{port}"
        self.ws = None
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.callbacks = []
        self.reconnect_delay = reconnect_delay
        self.button_state = 0

    def onData(self, callback):
        self.callbacks.append(callback)

    async def monitor(self):
        while True:
            try:
                async with connect(self.url, ping_interval=15, ping_timeout=30) as ws:
                    self.ws = ws
                    print(f"WebSocket connection opened to IMU server at {self.url}")

                    try:
                        async for message in ws:
                            self.parse(message)
                            for cb in list(self.callbacks):
                                try:
                                    if inspect.iscoroutinefunction(cb):
                                        await cb(self.yaw, self.pitch, self.roll, self.button_state)
                                    else:
                                        cb(self.yaw, self.pitch, self.roll, self.button_state)
                                except Exception as exc:
                                    print(f"IMU WebSocket callback error: {exc!r}")
                    except ConnectionClosed:
                        pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"Failed to connect to IMU WebSocket server at {self.url}: {exc}")
            finally:
                if self.ws is not None:
                    self.ws = None
                    print("WebSocket connection closed; retrying...")

            await asyncio.sleep(self.reconnect_delay)
    
    def update(self, yaw, pitch, roll):
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll

    def parse(self, data):
        if (len(data) < 12):
            return

        button_state = data[-1] # last byte is button state

        # take off the last byte, which is the button state
        data = data[:-1]

        # parse yaw, pitch, roll from data bytes, float32 each, in order
        try:
            self.yaw, self.pitch, self.roll = struct.unpack('fff', data)
            self.button_state = button_state
        except (ValueError, IndexError) as e:
            print(f"Error parsing IMU data: {e}")
