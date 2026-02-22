import asyncio
from datetime import datetime
import copy
import threading
import math
import struct
import re
import voice
import random

from sound_master import SoundMaster

PRINT_BEAT = False

class Settings:
    def __init__(self):
        self.modulation = 0
        self.volume = 0
        self.beats_per_loop = 8
        self.notify_ai = False
        self.notify_reset = False
        self.waiting_for_ai = False
        # todo eventually: live settings etc but dw for now

class Looper:
    def __init__(self, sm: "SoundMaster"):
        self.sm = sm

        self.gemini_client = voice.Voice()

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

    def add_action_description(self, description_list=None):
        if (description_list is None):
            return
        
        if (len(description_list) != 5):
            return
        
        self.topic_descriptions.append(description_list)

    def reset_loop(self, active):
        if active in self.loops:
            del self.loops[active]

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

    def next_instrument(self):
        self.active = (self.active + 1) % len(self.actions)
        print(f"Switched to instrument {self.active}")

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
        state.append(1 if self.settings.notify_ai else 0) # notify AI switch
        state.append(1 if self.settings.notify_reset else 0) # notify reset
        state.append(1 if self.settings.waiting_for_ai else 0) # waiting for AI response

        return state
    

    async def ai_refine_loop(self):
        """Send the active loop to Gemini for refinement and replace it with the response."""
        if self.active == -1:
            print("No active loop to refine.")
            return False
        
        self.active -= 1 
        if self.active < 0:
            self.active = len(self.actions) - 1

        prompt = self.convert_active_to_ai_readable()
        if not prompt:
            print("No prompt generated for AI refinement.")
            return False

        print(f"Sending loop to AI for refinement:\n------\n{prompt}\n------")

        pre_active = int(self.active) + 1 - 1
        self.settings.waiting_for_ai = True # set flag to indicate waiting for AI response

        try:
            # run the blocking Gemini call off the event loop
            response = await asyncio.to_thread(self.gemini_client.ask, prompt)
        except Exception as exc:
            print(f"AI refinement failed: {exc}")
            self.settings.waiting_for_ai = False # reset flag if AI refinement fails
            return False
        
        self.settings.waiting_for_ai = False # reset flag after receiving AI response

        if not response:
            print("AI returned an empty response.")
            return False

        if not self.convert_from_ai(response, pre_active):
            print("AI response could not be parsed into a loop.")
            return False

        # notify any subscribers that state changed
        for cb in self.update_callbacks:
            cb(self.get_state())

        return True

    def convert_active_to_ai_readable(self):
        """Return the kit.txt prompt with the active loop's hits inserted."""
        if self.active == -1:
            return ""

        try:
            with open("prompts/kit.txt", "r", encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError:
            return ""

        names = []
        if self.active < len(self.topic_descriptions):
            names = self.topic_descriptions[self.active]

        hits = []
        for action_time, finger_index in sorted(self.loops.get(self.active, []), key=lambda x: x[0]):
            name = names[finger_index] if finger_index < len(names) else f"Finger {finger_index}"
            beat_ts = (action_time / self.beat_length) % self.settings.beats_per_loop
            hits.append(f"{name}: {beat_ts:.3f}")

        hits_block = "\n".join(hits) if hits else "No hits recorded."

        vibes = [
            "chill",
            "upbeat",
            "hip-hop",
            "jazzy",
            "rock",
        ]

        return template.replace("$$$HITS$$$", hits_block).replace("$$VIBE$$", vibes[random.randint(0, len(vibes)-1)])

    def convert_from_ai(self, ai_response: str, active):
        print(f"AI response:\n{ai_response}")

        """Parse AI refined loop XML and replace the active loop. Returns True on success."""
        if active == -1:
            return False

        if active < len(self.topic_descriptions):
            names = self.topic_descriptions[active]
        else:
            names = [f"Finger {i}" for i in range(5)]

        name_to_finger = {n.lower(): i for i, n in enumerate(names)}

        notes = re.findall(r"<note>(.*?)</note>", ai_response, flags=re.DOTALL | re.IGNORECASE)

        new_hits = []
        for note in notes:
            name_match = re.search(r"<name>\s*(.*?)\s*</name>", note, flags=re.DOTALL | re.IGNORECASE)
            if not name_match:
                continue

            name = name_match.group(1).strip().lower()
            if name not in name_to_finger:
                continue

            finger_index = name_to_finger[name]

            for ts_str in re.findall(r"<timestamp>\s*([\d.]+)\s*</timestamp>", note, flags=re.DOTALL | re.IGNORECASE):
                try:
                    beat_val = float(ts_str)
                except ValueError:
                    continue

                beat_val = beat_val % self.settings.beats_per_loop
                time_sec = beat_val * self.beat_length
                new_hits.append((time_sec, finger_index))

        if not new_hits:
            return False

        new_hits.sort(key=lambda x: x[0])
        self.loops[active] = new_hits
        return True