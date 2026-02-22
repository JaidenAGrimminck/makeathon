import asyncio

import uart
import websockets
from websockets.exceptions import ConnectionClosed
import ip

uc0 = uart.UART('/dev/cu.usbmodem101', 250000)
uc1 = uart.UART('/dev/cu.usbmodem2101', 250000)

ip = ip.get_local_ip_robust() or "localhost"

connected_clients = set()

values = [
    0,0,0,0,0,0 # values
]

async def dispatch(msg, ws=None):
    # don't need anything fancy here since we're just broadcasting raw data, but this is where you could add server-side processing if needed
    pass

async def handleMsg(ws, path=None):
    connected_clients.add(ws)
    print(f"Client connected: {ws.remote_address}")
    try:
        async for message in ws:
            await dispatch(message, ws)
    except ConnectionClosed:
        pass
    finally:
        connected_clients.discard(ws)

def trim(s):
    # remove spaces
    return s.replace(" ", "")

async def handle_uart1(data, ws=None):
    await handle_uart(data, 1, ws)

async def handle_uart0(data, ws=None):
    await handle_uart(data, 0, ws)

last_data = []

async def handle_uart(data, side, ws=None):
    global values

    # should be string
    text = data.decode('utf-8').strip() # remove any trailing newline characters\

    # print(f"Received UART data: {text} (side {side})")

    # detect side by first occurrence of 0 or 1, default to 0
    side = 0
    for ch in text:
        if ch == '0':
            side = 0
            break
        if ch == '1':
            side = 1
            break
    
    nvals = text.split('Values: ')[-1].split(',') # get the part after "Values: " and split by comma
    nvals = [trim(n) for n in nvals] # trim spaces from each value
    if int(side) == 0:
        values[0] = int(nvals[0]) # thumb
        values[1] = int(nvals[1]) # index
        values[2] = int(nvals[2]) # middle
    else:
        values[3] = int(nvals[0]) # ring
        values[4] = int(nvals[1]) # pinky
        values[5] = int(nvals[2]) # extra
        # values[3] = int(0) # ring
        # values[4] = int(0) # pinky
        # values[5] = int(0) # extra

    # print(f"Received UART data: {values} (side {side})")

    # broadcast data
    for ws in list(connected_clients):
        try:
            # send as comma-separated string of values
            await ws.send(','.join(str(v) for v in values))
        except ConnectionClosed:
            connected_clients.discard(ws)
    pass    

async def start():
    async with websockets.serve(handleMsg, ip, 9999, ping_interval=30, ping_timeout=10) as server:
        print("Server started at ws://localhost:9999")
        await server.serve_forever()

# setup a server
async def main():
    print("Starting server...")
    uc0.onData(handle_uart0)
    uc1.onData(handle_uart1)
    websockets_task = asyncio.create_task(start())
    uart_task = asyncio.create_task(uc0.monitor())
    uart_task1 = asyncio.create_task(uc1.monitor())
    await asyncio.gather(websockets_task, uart_task, uart_task1)

if __name__ == "__main__":
    asyncio.run(main())