import time

from piano import PianoSampleLibrary
from notes_player import PolyphonicPlayer  # if you put PolyphonicPlayer in its own file
# If you pasted PolyphonicPlayer in the same script, just import/use it directly.

ROOT = "Piano"  # <-- change this
SR = 44100
BPM = 90
BEAT = 60.0 / BPM

piano = PianoSampleLibrary(ROOT)
player = PolyphonicPlayer(sr=SR)

def play_note(note: str, vel=0.8, dur_beats=1.0, gain=0.7):
    # vel can be float 0..1, closest=True helps if a note isn't present
    path = piano.path(note, vel, closest=True)
    player.trigger(path, gain=gain)
    time.sleep(BEAT * dur_beats)

def play_chord(notes, vel=0.7, dur_beats=1.0, gain=0.45):
    for n in notes:
        path = piano.path(n, vel, closest=True)
        player.trigger(path, gain=gain)
    time.sleep(BEAT * dur_beats)

try:
    # 8-bar phrase in C major (right hand)
    # Each bar is 4 beats.
    melody = [
        ("E4", 0.8, 1), ("G4", 0.8, 1), ("A4", 0.8, 1), ("G4", 0.8, 1),
        ("E4", 0.8, 1), ("D4", 0.75, 1), ("C4", 0.75, 2),

        ("D4", 0.8, 1), ("E4", 0.8, 1), ("G4", 0.85, 1), ("E4", 0.8, 1),
        ("D4", 0.75, 1), ("C4", 0.75, 1), ("D4", 0.75, 2),

        ("E4", 0.85, 1), ("G4", 0.85, 1), ("C5", 0.9, 1), ("B4", 0.85, 1),
        ("A4", 0.8, 1), ("G4", 0.8, 1), ("E4", 0.75, 2),

        ("D4", 0.8, 1), ("E4", 0.8, 1), ("G4", 0.85, 1), ("A4", 0.85, 1),
        ("G4", 0.8, 1), ("E4", 0.8, 1), ("D4", 0.75, 1), ("C4", 0.75, 1),
    ]

    # Simple left-hand chords (one per bar, held 4 beats)
    chords = [
        ["C3", "G3", "E4"],  # C
        ["A2", "E3", "C4"],  # Am
        ["F2", "C3", "A3"],  # F
        ["G2", "D3", "B3"],  # G
        ["C3", "G3", "E4"],  # C
        ["A2", "E3", "C4"],  # Am
        ["F2", "C3", "A3"],  # F
        ["G2", "D3", "B3"],  # G
    ]

    # Play: chord at start of each bar while melody runs
    melody_i = 0
    for bar in range(8):
        play_chord(chords[bar], vel=0.6, dur_beats=0.01, gain=0.35)  # trigger chord, don't wait

        beats_remaining = 4.0
        while beats_remaining > 1e-6 and melody_i < len(melody):
            note, vel, dur = melody[melody_i]
            dur = float(dur)
            if dur > beats_remaining:
                dur = beats_remaining
            play_note(note, vel=vel, dur_beats=dur, gain=0.7)
            beats_remaining -= dur
            melody_i += 1

        # If melody ended early in a bar, just wait out the bar
        if beats_remaining > 1e-6:
            time.sleep(BEAT * beats_remaining)

    time.sleep(1.5)  # let tails ring

finally:
    player.close()