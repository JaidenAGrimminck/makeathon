import asyncio
from datetime import datetime
import copy
import threading
import math
import struct

from sound_master import SoundMaster

PRINT_BEAT = False

class Settings:
    def __init__(self):
        self.modulation = 0
        self.volume = 0
        self.beats_per_loop = 8
        # todo eventually: live settings etc but dw for now

class Looper:
    def __init__(self, sm: "SoundMaster"):
        self.sm = sm

        self.loops = {} # under each index corresponding to , list of (time, action_num) tuples, sorted by time

        self.actions = []
        
        self.bpm = 120
        self.beat_length = 60.0 / self.bpm

        self.looping = False
        self.loop_start_time = None
        # active action index for recording; -1 when not recording
        self.active = -1

        self.beat_callbacks = [] # list of callbacks to call on each beat (8 beats per loop)
        self.update_callbacks = [] # list of callbacks to call on each update (when loop is updated)
        self.topic_descriptions = [] # optional descriptions for each action index, used for frontend display

        self.use_combo = [] # which actions will use a binary combo of fingers instead of individual fingers (for more complex actions)

        self.recording = False

        self.settings = Settings()


    def onBeat(self, callback):
        self.beat_callbacks.append(callback)

    def onUpdate(self, callback):
        self.update_callbacks.append(callback)
    
    def setRecording(self, recording):
        self.recording = recording

    def set_modulation(self, value: float):
        """Set pitch modulation in range [-1, 1]; applied as playback rate 0.5x..2x."""
        self.settings.modulation = max(-1.0, min(1.0, float(value)))
        target_rate = 2.0 ** self.settings.modulation
        self.sm.set_global_rate(target_rate)

    def set_volume(self, value: float):
        """Set master volume in range [-1, 1]; applied as gain 0.5x..2x."""
        self.settings.volume = max(-1.0, min(1.0, float(value)))
        target_gain = 2.0 ** self.settings.volume
        self.sm.set_master_gain(target_gain)

    """
    Adds a list of "5" actions (one per finger) to the looper's action list. Each action is a function that will be called when the corresponding finger is tapped.
    The action_list should be a list of 5 callables (or None for no action). The index in the list corresponds to the finger (0-4).
    Example:
    looper.add_action([
        lambda: print("Thumb tapped"),
        lambda: print("Index tapped"),
        None,
        lambda: print("Ring tapped"),
        lambda: print("Pinky tapped"),
    ])
    """
    def add_action(self, action_list=None):
        if (action_list is None):
            return
        
        if (len(action_list) != 5):
            return
        
        self.actions.append(action_list)

    def trigger_action(self, finger_index, active=-2, add_to_loop=True):
        if not self.looping:
            return
        
        if (active == -2):
            active = self.active
        
        if active == -1:
            return
        
        if self.actions[active][finger_index] is not None:
            threading.Thread(target=self.actions[active][finger_index]).start() # trigger action in separate thread to avoid blocking
            
            # check if have loop
            if active not in self.loops:
                self.loops[active] = []
            
            if add_to_loop and self.recording:
                # add to loop
                self.loops[active].append(((datetime.now() - self.loop_start_time).total_seconds(), finger_index))
                self.loops[active].sort(key=lambda x: x[0]) # sort by time
                print(f"Added action for finger {finger_index} at time {(datetime.now() - self.loop_start_time).total_seconds():.2f}s to loop {active}")

    def set_active(self, index):
        self.active = index

    def set_looping(self, looping):
        self.looping = looping

    async def start_loop(self, loop_index=0):        
        self.looping = True
        self.loop_start_time = datetime.now()

        loops_clone = copy.deepcopy(self.loops) # to prevent modification during iteration
        beats = 0
        beat_time = datetime.now()

        if self.looping:
            # first beat immediately on loop start
            for cb in self.beat_callbacks:
                cb(0)

        while self.looping:
            current_time = datetime.now() - self.loop_start_time
            
            for i in range(len(self.actions)):
                for action_time, finger_index in loops_clone.get(i, []):
                    #print(f"Checking action at {action_time:.2f}s (current time: {current_time.total_seconds():.2f}s)")
                    if action_time <= current_time.total_seconds():
                        #print(f"Triggering action for finger {finger_index} at time {action_time:.2f}s")

                        threading.Thread(target=self.actions[i][finger_index]).start() # trigger action in separate thread to avoid blocking

                        loops_clone[i].remove((action_time, finger_index)) # remove from loop to prevent retriggering

            await asyncio.sleep(0.01)
            
            # modulation now applied globally via SoundMaster

            current_time = datetime.now() - self.loop_start_time

            if ((datetime.now() - beat_time).total_seconds() >= self.beat_length):
                beats += 1
                beat_time = datetime.now() # reset beat time

                for cb in self.beat_callbacks:
                    cb(beats % self.settings.beats_per_loop)

                str_out = ""
                for b in range(beats):
                    str_out += "X "
                for b in range(self.settings.beats_per_loop - beats):
                    str_out += "- "
                
                if PRINT_BEAT: print(f"Beat: {str_out}")

            if (current_time.total_seconds() >= self.beat_length * self.settings.beats_per_loop): # end of loop
                self.loop_start_time = datetime.now() # reset loop time
                beat_time = datetime.now() # reset beat time
                loops_clone = copy.deepcopy(self.loops) # reset loop actions
                beats = 0

                if PRINT_BEAT: print("Beat: " + "X " * self.settings.beats_per_loop)

                for cb in self.beat_callbacks:
                    cb(beats % self.settings.beats_per_loop)
            
            for cb in self.update_callbacks:
                cb(self.get_state())

    def get_state(self):
        # returns a byte array representing the current state of the looper, including active loop, recording status, and modulation
        state = bytearray()
        state.append(self.active if self.active != -1 else 255) # active loop index
        state.append(1 if self.recording else 0) # recording status
        modulation_byte = int((self.settings.modulation + 1) / 2 * 255) # convert modulation from [-1, 1] to [0, 255]
        state.append(modulation_byte)
        
        state.append(self.settings.beats_per_loop) # beats per loop

        state.append(len(self.actions)) # number of actions
        for i in range(len(self.actions)):
            state.append(1 if i in self.loops else 0) # whether loop has actions
            if i in self.loops:
                state.append(len(self.loops[i])) # number of actions in loop
                for action_time, finger_index in self.loops[i]:
                    state.append(finger_index)
                    # convert action_time to float32 representation in milliseconds
                    time_ms = int(action_time * 1000)
                    time_bytes = struct.pack('<I', time_ms) # little-endian unsigned int
                    state.extend(time_bytes)

        volume_byte = int((self.settings.volume + 1) / 2 * 255) # convert volume from [-1, 1] to [0, 255]
        state.append(volume_byte)

        return state