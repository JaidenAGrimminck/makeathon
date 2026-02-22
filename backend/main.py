import wss
import asyncio
import glove
import uart
import player as drum_player
import pplayer as piano_player
import psplayer as synth_player
import sound_master
import looper
import imu
import ip

sm = sound_master.SoundMaster()
server = wss.Server()
# gloveL = glove.Glove(glove.Side.LEFT)
gloveR = glove.Glove(glove.Side.RIGHT)
gloveL = glove.GloveTouch(glove.Side.LEFT)


drum_player = drum_player.DrumPlayer(sm)
piano_player = piano_player.PianoPlayer(sm)
synth_player = synth_player.SynthPlayer(sm)

looper = looper.Looper(sm)

my_ip = ip.get_local_ip_robust() or "localhost"
print(f"Local IP address: {my_ip}")

imu = imu.IMU(my_ip, 9967)
uart = uart.UARTClient(my_ip, 9999)

def handle_uart_data(data):
    # 6 values, each seperated by commas
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    values = data.strip().split(',')[-6:] # get last 6 values
    values = [int(v) for v in values] # convert to floats

    
    gloveR.process_uart_values(values[:5]) # first 5 values are for gloveR

    # gloveR.fingers['thumb'] = values[5]
    # gloveR.fingers['index'] = values[6]
    # gloveR.fingers['middle'] = values[7]
    # gloveR.fingers['ring'] = values[8]
    # gloveR.fingers['pinky'] = values[9]

last_imu_data = (0.0, 0.0, 0.0)
last_yaw_sig = 0.0
looper_mod = 0.0

def handle_imu_data(yaw, pitch, roll, buttons=0b0000):
    global last_imu_data, looper_mod, last_yaw_sig
    diff = (yaw - last_imu_data[0], pitch - last_imu_data[1], roll - last_imu_data[2])
    dy = yaw - last_yaw_sig
    
    set_n = abs(dy) > 0.5

    if set_n:
        last_yaw_sig = yaw

        if buttons & 0b0001: # if first button is pressed, adjust modulation
            if dy > 0.5:
                looper_mod += 0.02
            elif dy < -0.5:
                looper_mod -= 0.02

            looper.set_modulation(looper_mod)


    if buttons & 0b0010: # if second button is pressed, adjust volume
        if dy > 0.5:
            looper.set_volume(looper.settings.volume + 0.02)
        elif dy < -0.5:
            looper.set_volume(looper.settings.volume - 0.02)


    last_imu_data = (yaw, pitch, roll)

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

    if msg[0] == 0x6c:
        # modulation
        modulation_value = (msg[1] / 255.0 - 0.5) * 2.0 # convert 0-255 to -1.0 to 1.0
        looper.set_modulation(modulation_value)

    if msg[0] == 0x99:
        # imu data
        imu.update_from_bytes(msg[1:]) # pass the 12 bytes of data after the header

async def main():
    looper.add_action([
        lambda: drum_player.play('kick'),
        lambda: drum_player.play('snare'),
        lambda: drum_player.play('hat'),
        lambda: drum_player.play('tom'),
        None,
    ])

    looper.add_action([
        lambda: piano_player.play_note('C4', vel=0.8, dur_beats=0.01, gain=0.4),
        lambda: piano_player.play_note('E4', vel=0.8, dur_beats=0.01, gain=0.4),
        lambda: piano_player.play_note('G4', vel=0.8, dur_beats=0.01, gain=0.4),
        lambda: piano_player.play_note('B4', vel=0.8, dur_beats=0.01, gain=0.4),
        lambda: piano_player.play_note('C5', vel=0.8, dur_beats=0.01, gain=0.4),
    ])

    looper.add_action([
        lambda: synth_player.play_chord([60, 64, 67, 71], vel=0.8, dur_beats=4, gain=0.30),  # Cmaj7
        lambda: synth_player.play_chord([62, 65, 69, 72], vel=0.8, dur_beats=4, gain=0.30),  # Dm7
        lambda: synth_player.play_chord([64, 67, 71, 74], vel=0.8, dur_beats=4, gain=0.30),  # Em7
        lambda: synth_player.play_chord([65, 69, 72, 76], vel=0.8, dur_beats=4, gain=0.30),  # Fmaj7
        lambda: synth_player.play_chord([67, 71, 74, 78], vel=0.8, dur_beats=4, gain=0.30),  # G7
    ])

    looper.onBeat(lambda beat: server.broadcast(bytearray([0x62, beat])))
    looper.onUpdate(lambda state: server.broadcast(bytearray([0x73]) + state)) # 's' for state update
    looper.setRecording(False) # start with recording off

    looper.set_active(0) # set piano loop as active
    looper.set_looping(True)

    gloveR.on_tap('thumb', lambda: looper.trigger_action(0))
    gloveR.on_tap('index', lambda: looper.trigger_action(1))
    gloveR.on_tap('middle', lambda: looper.trigger_action(2))
    gloveR.on_tap('ring', lambda: looper.trigger_action(3))
    gloveR.on_tap('pinky', lambda: looper.trigger_action(4))

    uart.onData(handle_uart_data)
    imu.onData(handle_imu_data)
    server.onMessage(on_msg)

    server_task = asyncio.create_task(server.start())
    uart_task = asyncio.create_task(uart.monitor())
    imu_task = asyncio.create_task(imu.monitor())
    looper_task = asyncio.create_task(looper.start_loop(0))  # start first loop

    await asyncio.gather(server_task, uart_task, looper_task, imu_task)


if __name__ == "__main__":
    asyncio.run(main())