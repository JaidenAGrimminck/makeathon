import time

from piano import PianoSampleLibrary
from notes_player import PolyphonicPlayer  # if you put PolyphonicPlayer in its own file
# If you pasted PolyphonicPlayer in the same script, just import/use it directly.


class PianoPlayer:
    def __init__(self, sound_master, folder="Piano", BPM=90):
        self.sm = sound_master
        self.piano = PianoSampleLibrary(folder)
        self.player = PolyphonicPlayer(sr=44100)
        self.BPM = BPM
        self.BEAT = 60.0 / BPM

    def play_note(self, note: str, vel=0.8, dur_beats=1.0, gain=0.7):
        # vel can be float 0..1, closest=True helps if a note isn't present
        path = self.piano.path(note, vel, closest=True)
        self.player.trigger(path, gain=gain)
        time.sleep(self.BEAT * dur_beats)

    def play_chord(self, notes, vel=0.7, dur_beats=1.0, gain=0.45):
        for n in notes:
            path = self.piano.path(n, vel, closest=True)
            self.player.trigger(path, gain=gain)
        time.sleep(self.BEAT * dur_beats)

