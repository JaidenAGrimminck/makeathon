#!/usr/bin/env python3
"""
modern_synth.py
Pure-Python synth (numpy + sounddevice) with a few "modern" style presets:
- supersaw lead
- pluck
- bass
- pad

Usage:
  python modern_synth.py --preset supersaw
  python modern_synth.py --preset bass
  python modern_synth.py --preset pluck
  python modern_synth.py --preset pad
"""

import argparse
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np
import sounddevice as sd


# ----------------------------
# Basics
# ----------------------------
def midi_to_freq(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


def db_to_lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def softclip_tanh(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    return np.tanh(x * drive)


def one_pole_lowpass(x: np.ndarray, sr: int, cutoff_hz: float) -> np.ndarray:
    """Simple 1-pole LPF; cutoff is approximate."""
    cutoff_hz = float(np.clip(cutoff_hz, 20.0, sr * 0.45))
    # alpha from RC filter: alpha = dt / (RC + dt)
    dt = 1.0 / sr
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = dt / (rc + dt)
    y = np.empty_like(x)
    y0 = 0.0
    for i in range(len(x)):
        y0 = y0 + alpha * (x[i] - y0)
        y[i] = y0
    return y


def adsr_envelope(n: int, sr: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    """
    ADSR in seconds; sustain is level [0..1].
    Note: This envelope assumes full note length includes release.
    We'll build as: attack -> decay -> sustain -> release (end).
    """
    a_samp = max(1, int(a * sr))
    d_samp = max(1, int(d * sr))
    r_samp = max(1, int(r * sr))
    # sustain samples are whatever remains
    sustain_samp = max(0, n - (a_samp + d_samp + r_samp))

    # Attack: 0 -> 1
    attack = np.linspace(0.0, 1.0, a_samp, endpoint=False, dtype=np.float32)
    # Decay: 1 -> s
    decay = np.linspace(1.0, float(s), d_samp, endpoint=False, dtype=np.float32)
    # Sustain: flat at s
    sustain = np.full((sustain_samp,), float(s), dtype=np.float32)
    # Release: s -> 0
    release = np.linspace(float(s), 0.0, r_samp, endpoint=True, dtype=np.float32)

    env = np.concatenate([attack, decay, sustain, release])
    # Trim/pad to exact length
    if len(env) > n:
        env = env[:n]
    elif len(env) < n:
        env = np.pad(env, (0, n - len(env)), mode="constant")
    return env


# ----------------------------
# Oscillators
# ----------------------------
def osc_saw(phase: np.ndarray) -> np.ndarray:
    # saw: range [-1, 1]
    return (2.0 * (phase - np.floor(phase + 0.5))).astype(np.float32)


def osc_square(phase: np.ndarray, pw: float = 0.5) -> np.ndarray:
    return np.where((phase % 1.0) < pw, 1.0, -1.0).astype(np.float32)


def osc_sine(phase: np.ndarray) -> np.ndarray:
    return np.sin(2.0 * np.pi * phase).astype(np.float32)


@dataclass
class Preset:
    name: str
    # Osc mix
    osc: str  # "supersaw", "saw", "square", "sine"
    voices: int = 1
    detune_cents: float = 0.0
    # Amp envelope
    a: float = 0.005
    d: float = 0.10
    s: float = 0.6
    r: float = 0.12
    # Filter
    cutoff: float = 8000.0
    cutoff_keytrack: float = 0.0  # adds Hz per MIDI note step (rough)
    # Character
    drive_db: float = 0.0
    # Stereo width
    width: float = 0.3  # 0..1
    # Optional pitch LFO (subtle movement for pads/leads)
    lfo_hz: float = 0.0
    lfo_depth_cents: float = 0.0


PRESETS = {
    "supersaw": Preset(
        name="supersaw",
        osc="supersaw",
        voices=7,
        detune_cents=18.0,
        a=0.003, d=0.12, s=0.55, r=0.18,
        cutoff=6500.0,
        drive_db=6.0,
        width=0.9,
        lfo_hz=5.5,
        lfo_depth_cents=3.0,
    ),
    "pluck": Preset(
        name="pluck",
        osc="saw",
        voices=2,
        detune_cents=6.0,
        a=0.001, d=0.10, s=0.0, r=0.10,
        cutoff=5200.0,
        drive_db=3.0,
        width=0.5,
        lfo_hz=0.0,
        lfo_depth_cents=0.0,
    ),
    "bass": Preset(
        name="bass",
        osc="square",
        voices=1,
        detune_cents=0.0,
        a=0.002, d=0.08, s=0.45, r=0.08,
        cutoff=1200.0,
        cutoff_keytrack=18.0,  # brighten a bit with higher notes
        drive_db=9.0,
        width=0.1,
        lfo_hz=0.0,
        lfo_depth_cents=0.0,
    ),
    "pad": Preset(
        name="pad",
        osc="supersaw",
        voices=5,
        detune_cents=10.0,
        a=0.25, d=0.40, s=0.75, r=0.65,
        cutoff=2400.0,
        drive_db=0.0,
        width=0.85,
        lfo_hz=0.25,
        lfo_depth_cents=6.0,
    ),
}


# ----------------------------
# Synth voice rendering
# ----------------------------
def make_phase(freq_hz: np.ndarray, sr: int) -> np.ndarray:
    """freq_hz may be scalar or per-sample; returns phase in cycles [0..)."""
    # phase increment = freq / sr
    return np.cumsum(freq_hz / sr, dtype=np.float64)


def cents_to_ratio(cents: float) -> float:
    return 2.0 ** (cents / 1200.0)


def render_note(
    midi_note: int,
    duration_s: float,
    velocity: float,
    preset: Preset,
    sr: int,
) -> np.ndarray:
    """
    Returns stereo float32 array shape (n, 2), range roughly [-1, 1].
    """
    n = max(1, int(duration_s * sr))
    t = np.arange(n, dtype=np.float32) / sr

    base_freq = midi_to_freq(midi_note)

    # Optional pitch LFO
    if preset.lfo_hz > 0.0 and preset.lfo_depth_cents != 0.0:
        lfo = np.sin(2.0 * np.pi * preset.lfo_hz * t).astype(np.float32)
        freq = base_freq * (2.0 ** ((lfo * preset.lfo_depth_cents) / 1200.0))
        freq = freq.astype(np.float64)
    else:
        freq = np.full(n, base_freq, dtype=np.float64)

    # Voice detunes and pans
    voices = max(1, int(preset.voices))
    if preset.osc == "supersaw":
        # spread detune around 0 cents
        # e.g., 7 voices -> [-3..+3] steps
        idx = np.linspace(-(voices - 1) / 2.0, (voices - 1) / 2.0, voices)
        detunes = idx * (preset.detune_cents / max(1.0, (voices - 1) / 2.0))
    else:
        detunes = np.linspace(-preset.detune_cents, preset.detune_cents, voices)

    # Stereo panning for width
    # pan in [-1..1], left=(1-pan)/2, right=(1+pan)/2
    pans = np.linspace(-1.0, 1.0, voices, dtype=np.float32) * float(np.clip(preset.width, 0.0, 1.0))

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    for i in range(voices):
        ratio = cents_to_ratio(float(detunes[i]))
        vfreq = (freq * ratio).astype(np.float64)
        phase = make_phase(vfreq, sr)  # cycles

        if preset.osc in ("supersaw", "saw"):
            sig = osc_saw(phase)
        elif preset.osc == "square":
            sig = osc_square(phase, pw=0.5)
        elif preset.osc == "sine":
            sig = osc_sine(phase)
        else:
            sig = osc_saw(phase)

        pan = float(pans[i])
        l_gain = math.sqrt((1.0 - pan) * 0.5)
        r_gain = math.sqrt((1.0 + pan) * 0.5)
        left += sig * l_gain
        right += sig * r_gain

    # Normalize by voices
    left /= voices
    right /= voices

    # Amp envelope
    env = adsr_envelope(n, sr, preset.a, preset.d, preset.s, preset.r)
    amp = float(np.clip(velocity, 0.0, 1.0))
    left *= env * amp
    right *= env * amp

    # Filter (keytracking is coarse; good enough for “brightens as you go up”)
    cutoff = float(preset.cutoff + preset.cutoff_keytrack * (midi_note - 60))
    left = one_pole_lowpass(left, sr, cutoff)
    right = one_pole_lowpass(right, sr, cutoff)

    # Drive / saturation
    drive = db_to_lin(float(preset.drive_db))
    left = softclip_tanh(left, drive=drive)
    right = softclip_tanh(right, drive=drive)

    # Tiny DC cleanup (optional)
    left -= np.mean(left)
    right -= np.mean(right)

    out = np.stack([left, right], axis=1).astype(np.float32)
    return out


# ----------------------------
# Sequencing helpers
# ----------------------------
NoteEvent = Tuple[float, float, int, float]  # (start_s, dur_s, midi_note, vel)


def mix_events(events: List[NoteEvent], preset: Preset, sr: int) -> np.ndarray:
    if not events:
        return np.zeros((1, 2), dtype=np.float32)

    end_time = max(s + d for (s, d, _, _) in events)
    n_total = int(end_time * sr) + 1
    mix = np.zeros((n_total, 2), dtype=np.float32)

    for start_s, dur_s, midi_note, vel in events:
        start_i = int(start_s * sr)
        note = render_note(midi_note, dur_s, vel, preset, sr)
        end_i = min(n_total, start_i + note.shape[0])
        mix[start_i:end_i] += note[: end_i - start_i]

    # Gentle limiter
    peak = float(np.max(np.abs(mix))) if mix.size else 1.0
    if peak > 0.98:
        mix *= (0.98 / peak)
    return mix


def demo_sequence(preset_name: str, bpm: float) -> List[NoteEvent]:
    """
    Short modern-ish loop:
    - pad: simple chord progression
    - supersaw/pluck: melody
    - bass: bassline
    """
    beat = 60.0 / bpm

    def at(b: float) -> float:
        return b * beat

    events: List[NoteEvent] = []

    # A minor-ish progression (Am - F - C - G) over 8 beats
    chords = [
        (0.0, [57, 60, 64]),  # A3 C4 E4
        (2.0, [53, 57, 60]),  # F3 A3 C4
        (4.0, [48, 52, 55]),  # C3 E3 G3
        (6.0, [55, 59, 62]),  # G3 B3 D4
    ]

    if preset_name == "pad":
        for start_b, notes in chords:
            for n in notes:
                events.append((at(start_b), at(2.0), n, 0.75))

    if preset_name in ("supersaw", "pluck"):
        # melody over 8 beats
        melody = [
            (0.0, 0.5, 72), (0.5, 0.5, 76), (1.0, 0.5, 79), (1.5, 0.5, 76),
            (2.0, 0.5, 72), (2.5, 0.5, 74), (3.0, 1.0, 76),
            (4.0, 0.5, 72), (4.5, 0.5, 76), (5.0, 0.5, 79), (5.5, 0.5, 81),
            (6.0, 0.5, 79), (6.5, 0.5, 76), (7.0, 1.0, 74),
        ]
        for b, d, n in melody:
            events.append((at(b), at(d), n, 0.9))

    if preset_name == "bass":
        # simple bassline
        bass = [
            (0.0, 0.5, 33), (0.5, 0.5, 33), (1.0, 1.0, 33),
            (2.0, 0.5, 29), (2.5, 0.5, 29), (3.0, 1.0, 29),
            (4.0, 0.5, 24), (4.5, 0.5, 24), (5.0, 1.0, 24),
            (6.0, 0.5, 31), (6.5, 0.5, 31), (7.0, 1.0, 31),
        ]
        for b, d, n in bass:
            events.append((at(b), at(d), n, 0.95))

    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="supersaw")
    parser.add_argument("--bpm", type=float, default=128.0)
    parser.add_argument("--sr", type=int, default=48000)
    parser.add_argument("--demo", action="store_true", help="Play a built-in demo sequence (default).")
    parser.add_argument("--note", type=int, default=None, help="Play one MIDI note instead of demo.")
    parser.add_argument("--dur", type=float, default=0.6, help="Duration for --note in seconds.")
    parser.add_argument("--vel", type=float, default=0.9, help="Velocity 0..1 for --note.")
    args = parser.parse_args()

    preset = PRESETS[args.preset]
    sr = args.sr

    if args.note is not None:
        audio = render_note(args.note, args.dur, args.vel, preset, sr)
    else:
        # default: demo loop of 8 beats
        events = demo_sequence(args.preset, args.bpm)
        audio = mix_events(events, preset, sr)

    sd.play(audio, samplerate=sr, blocking=True)


if __name__ == "__main__":
    main()