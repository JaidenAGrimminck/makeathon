import serial
import asyncio

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
                data = self.ser.readline().decode('utf-8').strip()
                for callback in self.callbacks:
                    callback(data)
            await asyncio.sleep(0.1)