import enum
from time import time


class Side(enum.Enum):
    LEFT = 1
    RIGHT = 2

class Glove:
    def __init__(self, side: Side):
        self.side = side
        
        self.fingers = {
            'thumb': 0,
            'index': 0,
            'middle': 0,
            'ring': 0,
            'pinky': 0
        }
        
        self.active = {
            'thumb': False,
            'index': False,
            'middle': False,
            'ring': False,
            'pinky': False
        }
        
        self.last_active = {
            'thumb': 0,
            'index': 0,
            'middle': 0,
            'ring': 0,
            'pinky': 0
        }

        self.threshholds = {
            'thumb': 100,
            'index': 100,
            'middle': 100,
            'ring': 100,
            'pinky': 100
        }

        self.min_time = 0.22 # minimum time in seconds between taps to prevent noise

        self.on_tap_callbacks = {
            'thumb': [],
            'index': [],
            'middle': [],
            'ring': [],
            'pinky': []
        }
    
    def process_uart_values(self, values):
        #print(values)
        for i, finger in enumerate(['thumb', 'index', 'middle', 'ring', 'pinky']):
            self.fingers[finger] = values[i]
            if values[i] > self.threshholds[finger]:
                if not self.active[finger] and time() - self.last_active[finger] > self.min_time:
                    self.active[finger] = True
                    print("Finger {} is now active with value {} (time since {})".format(finger, values[i], time() - self.last_active[finger]))
                    self.last_active[finger] = time()
                    # Trigger tap callback
                    for callback in self.on_tap_callbacks[finger]:
                        callback()
            else:
                self.active[finger] = False

    def on_tap(self, finger, callback):
        if finger in self.on_tap_callbacks:
            self.on_tap_callbacks[finger].append(callback)

    def tap(self, finger):
        if finger in self.fingers:
            self.fingers[finger] = 1
            # Trigger any callbacks associated with this finger tap
            for callback in self.on_tap_callbacks[finger]:
                callback()

    def get_state(self):
        return self.fingers

class GloveTouch:
    def __init__(self, side: Side):
        self.side = side
        
        self.fingers = {
            'thumb': {
                'top': False,
                'middle': False,
            },
            'index': {
                'top': False,
                'middle': False,
            },
            'middle': {
                'top': False,
                'middle': False,
            },
            'ring': {
                'top': False,
                'middle': False,
            },
            'pinky': {
                'top': False,
                'middle': False,
            }
        }

    def update_touch(self, finger, position, is_touching):
        if finger in self.fingers and position in self.fingers[finger]:
            self.fingers[finger][position] = is_touching
    
    def get_state(self):
        return self.fingers