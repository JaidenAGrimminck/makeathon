import wss
import asyncio
import glove
import uart
import player as drum_player
import pplayer as piano_player
import sound_master

sm = sound_master.SoundMaster()
server = wss.Server()
# gloveL = glove.Glove(glove.Side.LEFT)
gloveR = glove.Glove(glove.Side.RIGHT)

drum_player = drum_player.DrumPlayer(sm)
piano_player = piano_player.PianoPlayer(sm)


uart = uart.UART('/dev/ttyUSB0')

def handle_uart_data(data):
    # 10 values expected: 5 fingers * 2 (side + value) * 4 bytes each
    values = []
    checksum = 0
    for i in range(0, len(data), 4):
        if i + 4 > len(data):
            print(f"Warning: incomplete data chunk at index {i}")
            break
        chunk = data[i:i+4]
        try:
            value = int(chunk)
            values.append(value)
            checksum = checksum ^ value
        except ValueError:
            print(f"Warning: non-integer data chunk '{chunk}' at index {i}")
            continue
    
    final_byte = values[-1] if values else None
    if final_byte != checksum:
        print(f"Warning: checksum mismatch. Calculated {checksum}, got {final_byte}")
        return
    
    gloveR.fingers['thumb'] = values[0]
    gloveR.fingers['index'] = values[1]
    gloveR.fingers['middle'] = values[2]
    gloveR.fingers['ring'] = values[3]
    gloveR.fingers['pinky'] = values[4]

    # gloveR.fingers['thumb'] = values[5]
    # gloveR.fingers['index'] = values[6]
    # gloveR.fingers['middle'] = values[7]
    # gloveR.fingers['ring'] = values[8]
    # gloveR.fingers['pinky'] = values[9]

async def on_msg(msg, ws):
    if msg[0] == 0x67:
        # setting values of gloveR fingers
        if msg[1] == 0:
            gloveR.tap('thumb')
        elif msg[1] == 1:
            gloveR.tap('index')
        elif msg[1] == 2:
            gloveR.tap('middle')
        elif msg[1] == 3:
            gloveR.tap('ring')
        elif msg[1] == 4:
            gloveR.tap('pinky')

async def main():
    gloveR.on_tap('thumb', lambda: drum_player.play('kick'))
    gloveR.on_tap('index', lambda: drum_player.play('snare'))
    gloveR.on_tap('middle', lambda: drum_player.play('hat'))
    gloveR.on_tap('ring', lambda: drum_player.play('tom'))

    gloveR.on_tap('thumb', lambda: piano_player.play_note('C4', vel=0.8, dur_beats=0.01, gain=0.4))
    gloveR.on_tap('index', lambda: piano_player.play_note('E4', vel=0.8, dur_beats=0.01, gain=0.4))
    gloveR.on_tap('middle', lambda: piano_player.play_note('G4', vel=0.8, dur_beats=0.01, gain=0.4))
    gloveR.on_tap('ring', lambda: piano_player.play_note('B4', vel=0.8, dur_beats=0.01, gain=0.4))
    gloveR.on_tap('pinky', lambda: piano_player.play_note('C5', vel=0.8, dur_beats=0.01, gain=0.4))

    uart.onData(handle_uart_data)
    server.onMessage(on_msg)

    server_task = asyncio.create_task(server.start())
    uart_task = asyncio.create_task(uart.monitor())
    await asyncio.gather(server_task, uart_task)


if __name__ == "__main__":
    asyncio.run(main())