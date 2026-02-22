import asyncio
import inspect

import serial
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

class UARTClient:
    def __init__(self, host, port, reconnect_delay: float = 2.0):
        self.host = host
        self.port = port
        self.url = f"ws://{host}:{port}"
        self.ws = None
        self.callbacks = []
        self.reconnect_delay = reconnect_delay

    def onData(self, callback):
        self.callbacks.append(callback)

    async def monitor(self):
        while True:
            try:
                async with connect(self.url, ping_interval=15, ping_timeout=30) as ws:
                    self.ws = ws
                    print(f"WebSocket connection opened to UART server at {self.url}")

                    try:
                        async for message in ws:
                            for cb in list(self.callbacks):
                                try:
                                    if inspect.iscoroutinefunction(cb):
                                        await cb(message)
                                    else:
                                        cb(message)
                                except Exception as exc:
                                    print(f"UART WebSocket callback error: {exc!r}")
                    except ConnectionClosed:
                        pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"Failed to connect to UART WebSocket server at {self.url}: {exc}")
            finally:
                if self.ws is not None:
                    self.ws = None
                    print("WebSocket connection closed; retrying...")

            await asyncio.sleep(self.reconnect_delay)



class UART:
    def __init__(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

        self.callbacks = []

    def onData(self, callback):
        self.callbacks.append(callback)

    async def monitor(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate)
        except serial.SerialException as e:
            print(f"Failed to open serial port {self.port}: {e}")
            return

        while True:
            if self.ser.in_waiting > 0:
                # get all data
                data = self.ser.read(self.ser.in_waiting)
                lines = data.split(b'\n')
                for line in lines:
                    if line.strip():  # only process non-empty lines
                        for callback in self.callbacks:
                            await callback(line)
            await asyncio.sleep(0.001)