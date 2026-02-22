import enum


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

        self.on_tap_callbacks = {
            'thumb': [],
            'index': [],
            'middle': [],
            'ring': [],
            'pinky': []
        }
    
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

