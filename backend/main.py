from time import time

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
import threading

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

third_last = False
third_last_change = 0

third_down_time = 0
tdn = False
atdn = False

fourth_last = False
fourth_last_change = 0

fourth_down_time = 0
fdn = False
afdn = False


def handle_imu_data(yaw, pitch, roll, buttons=0b0000):
    global last_imu_data, looper_mod, last_yaw_sig, third_last, third_last_change, fourth_last, fourth_last_change, fourth_down_time, third_down_time, tdn, fdn, atdn, afdn
    diff = (yaw - last_imu_data[0], pitch - last_imu_data[1], roll - last_imu_data[2])
    dy = yaw - last_yaw_sig
    
    nb = 0
    for i in range(4):
        if (buttons & (1 << i)) > 0:
            nb |= (1 << (3 - i))
    buttons = nb

    set_n = abs(dy) > 0.5

    if set_n:
        last_yaw_sig = yaw

        if (buttons & 0b0001) > 0: # if first button is pressed, adjust modulation
            adj = False
            if dy > 0.5:
                adj = True
                looper_mod += 0.02
            elif dy < -0.5:
                adj = True
                looper_mod -= 0.02

            looper.set_modulation(looper_mod)
            if adj: print(f"Modulation: {looper.settings.modulation:.2f}")


    if (buttons & 0b0010) > 0: # if second button is pressed, adjust volume
        adj = False
        if dy > 0.5:
            looper.set_volume(looper.settings.volume + 0.02)
            adj = True
        elif dy < -0.5:
            looper.set_volume(looper.settings.volume - 0.02)
            adj = True
        
        if adj: print(f"Volume: {looper.settings.volume:.2f}")


    if (buttons & 0b0100) > 0: # if third button is pressed, toggle recording
        if not third_last and time() - third_last_change > 0.2:
            looper.setRecording(not looper.recording)
            print(f"Recording: {looper.recording}")
            third_last_change = time()
            third_down_time = time()
            tdn = False # reset AI switch trigger when button is pressed
            atdn = False # reset AI switch trigger when button is pressed

        if third_last and time() - third_down_time > 1.0 and not tdn: # if held for more than 1 second, notify AI switch
            tdn = True
            print("reset loop triggered!")
            looper.settings.notify_reset = True # set flag to notify loop reset in main loop
        
        if third_last and time() - third_down_time > 2.0 and not atdn: # if held for more than 2 seconds, reset loop
            atdn = True
            looper.reset_loop(looper.active)
            print("Loop reset!")
            looper.settings.notify_reset = False # reset flag after action is triggered
    else:
        looper.settings.notify_reset = False # reset flag if button is released
        
    third_last = bool(buttons & 0b0100)


    if (buttons & 0b1000) > 0: # if fourth button is pressed, toggle looping
        if not fourth_last and time() - fourth_last_change > 0.2:
            looper.next_instrument()
            fourth_last_change = time()
            fourth_down_time = time()
            print(f"Switched to instrument {looper.active}")
            fdn = False # reset AI switch trigger when button is pressed
            afdn = False
        
        if fourth_last and time() - fourth_down_time > 1.0 and not fdn: # if held for more than 1 second, notify AI switch
            fdn = True
            print("AI switch triggered!")
            looper.settings.notify_ai = True # set flag to notify AI switch in main loop

        if fourth_last and time() - fourth_down_time > 2.0 and not afdn: # if held for more than 2 seconds, reset loop
            afdn = True
            # trigger ai switch here
            print("AI switch action triggered!")
            looper.settings.notify_ai = False # reset flag after action is triggered

            def runRefine():
                # it's an async thread so we need to run it in an event loop
                asyncio.run(looper.ai_refine_loop())

            threading.Thread(target=runRefine).start() # run AI refinement in separate thread to avoid blocking main loop
    else:
        looper.settings.notify_ai = False # reset AI switch flag if button is released
            


    fourth_last = bool(buttons & 0b1000)
        

    last_imu_data = (yaw, pitch, roll)

async def on_msg(msg, ws):
    if msg[0] == 0x67:
        # print(f"Received tap message: {msg}")
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

    if msg[0] == 0x10:
        if msg[1] == 3:
            handle_imu_data(0, 0, 0, 0b0001)
        elif msg[1] == 2:
            handle_imu_data(0, 0, 0, 0b0010)
        elif msg[1] == 1:
            handle_imu_data(0, 0, 0, 0b0100)
        elif msg[1] == 0:
            handle_imu_data(0, 0, 0, 0b1000)
    
    # reset
    if msg[0] == 0x12:
        handle_imu_data(0,0,0, 0)

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
        None,
        lambda: drum_player.play('tom'),
    ])

    looper.add_action_description([
        "Kick",
        "Snare",
        "Hat",
        "None",
        "Tom",
    ])

    looper.add_action([
        lambda: piano_player.play_note('C4', vel=0.8, dur_beats=0.01, gain=0.4),
        lambda: piano_player.play_note('E4', vel=0.8, dur_beats=0.01, gain=0.4),
        lambda: piano_player.play_note('G4', vel=0.8, dur_beats=0.01, gain=0.4),
        lambda: piano_player.play_note('B4', vel=0.8, dur_beats=0.01, gain=0.4),
        None, #piano_player.play_note('C5', vel=0.8, dur_beats=0.01, gain=0.4),
    ])

    looper.add_action_description([
        "C4 (Piano)",
        "E4 (Piano)",
        "G4 (Piano)",
        "B4 (Piano)",
        "None", # "C5 (Piano)",
    ])

    looper.add_action([
        lambda: synth_player.play_chord([60, 64, 67, 71], vel=0.8, dur_beats=4, gain=0.30),  # Cmaj7
        lambda: synth_player.play_chord([62, 65, 69, 72], vel=0.8, dur_beats=4, gain=0.30),  # Dm7
        lambda: synth_player.play_chord([64, 67, 71, 74], vel=0.8, dur_beats=4, gain=0.30),  # Em7
        lambda: synth_player.play_chord([65, 69, 72, 76], vel=0.8, dur_beats=4, gain=0.30),  # Fmaj7
        None#lambda: synth_player.play_chord([67, 71, 74, 78], vel=0.8, dur_beats=4, gain=0.30),  # G7
    ])

    looper.add_action_description([
        "Cmaj7 (Synth)",
        "Dm7 (Synth)",
        "Em7 (Synth)",
        "Fmaj7 (Synth)",
        #"G7 (Synth)",
        None
    ])

    looper.onBeat(lambda beat: server.broadcast(bytearray([0x62, beat])))
    looper.onUpdate(lambda state: server.broadcast(bytearray([0x73]) + state)) # 's' for state update
    looper.setRecording(False) # start with recording off

    looper.set_active(2) # set piano loop as active
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