import uart
import websockets
import asyncio
import struct
import ip

uc = uart.UART('/dev/tty.usbserial-110', 115200)

ip = ip.get_local_ip_robust() or "localhost"

connected_clients = set()

async def dispatch(msg, ws=None):
    # don't need anything fancy here since we're just broadcasting raw data, but this is where you could add server-side processing if needed
    pass

async def handleMsg(ws, path=None):
    connected_clients.add(ws)
    print(f"Client connected: {ws.remote_address}")
    try:
        async for message in ws:
            await dispatch(message, ws)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(ws)

async def handle_uart(data):
    # should be string
    if isinstance(data, bytes):
        data = data.decode('utf-8')

    data = data.strip() # remove any trailing newline characters
    # last three numbers
    numbers = data.split('\t')[-4:]
    # yaw pitch roll
    print(f"Received UART data: {numbers}")

    last_num = numbers.pop() # remove last number, which is the button state
    button_state = 0
    for i in range(len(last_num)):
        button_state |= (1 << i) if last_num[i] == '1' else 0

    byte_arr = bytearray([]) # start byte
    for num in numbers:
        try:
            byte_arr.extend(struct.pack('f', float(num))) # convert to float and pack as 4 bytes
        except ValueError:
            print(f"Could not convert '{num}' to float. Skipping.")
            continue

    byte_arr.append(button_state) # append button state as last byte

    # broadcast data
    for ws in connected_clients:
        try:
            await ws.send(byte_arr)
        except websockets.exceptions.ConnectionClosed:
            connected_clients.discard(ws)
    pass    

async def start():
    async with websockets.serve(handleMsg, ip, 9967, ping_interval=30, ping_timeout=10) as server:
        print(f"Server started at ws://{ip}:9967")
        await server.serve_forever()

# setup a server
async def main():
    print("Starting server...")
    uc.onData(handle_uart)
    websockets_task = asyncio.create_task(start())
    uart_task = asyncio.create_task(uc.monitor())
    await asyncio.gather(websockets_task, uart_task)


if __name__ == "__main__":
    asyncio.run(main())