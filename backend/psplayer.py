
from typing import Iterable, Sequence

from modern_synth import PRESETS, mix_events, render_note


class SynthPlayer:
    """Lightweight modern synth wrapper that renders to numpy and pipes into SoundMaster."""

    def __init__(self, sound_master, preset: str = "pad", bpm: float = 120.0):
        self.sm = sound_master
        self.sr = getattr(sound_master, "sr", 44100)
        self.bpm = float(bpm)
        self.beat = 60.0 / self.bpm
        self.set_preset(preset)

    def set_preset(self, preset: str) -> None:
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset '{preset}'. Options: {sorted(PRESETS)}")
        self.preset_name = preset
        self.preset = PRESETS[preset]

    def _ensure_midi(self, note) -> int:
        if isinstance(note, (int, float)):
            return int(note)
        raise TypeError("note must be a MIDI integer")

    def play_note(self, note: int, vel: float = 0.8, dur_beats: float = 1.0, gain: float = 0.7) -> int:
        midi = self._ensure_midi(note)
        dur_s = float(dur_beats) * self.beat
        audio = render_note(midi, dur_s, float(vel), self.preset, self.sr)
        return self.sm.add(audio, gain=float(gain))

    def play_chord(
        self,
        notes: Iterable[int],
        vel: float = 0.7,
        dur_beats: float = 1.0,
        gain: float = 0.45,
    ) -> int:
        midi_notes: Sequence[int] = [self._ensure_midi(n) for n in notes]
        dur_s = float(dur_beats) * self.beat

        # Build simultaneous events at t=0 for all notes to keep them aligned.
        events = [(0.0, dur_s, n, float(vel)) for n in midi_notes]
        audio = mix_events(events, self.preset, self.sr)
        return self.sm.add(audio, gain=float(gain))