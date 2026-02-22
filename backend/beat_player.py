from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from drum import DrumSampleLibrary, SampleMeta
from sound_master import SoundMaster


# -------- Audio IO helpers --------
def _read_audio(path: Path):
    """
    Returns (audio: np.ndarray [frames, channels], sr: int)

    Requires: soundfile
    """
    import soundfile as sf  # pip install soundfile
    audio, sr = sf.read(str(path), always_2d=True)
    audio = audio.astype(np.float32, copy=False)
    return audio, int(sr)


def _resample_linear(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return audio
    src_len = audio.shape[0]
    dst_len = int(round(src_len * (dst_sr / src_sr)))
    if dst_len <= 1:
        return audio[:1]

    x_old = np.linspace(0.0, 1.0, num=src_len, endpoint=True, dtype=np.float64)
    x_new = np.linspace(0.0, 1.0, num=dst_len, endpoint=True, dtype=np.float64)

    out = np.zeros((dst_len, audio.shape[1]), dtype=np.float32)
    for ch in range(audio.shape[1]):
        out[:, ch] = np.interp(x_new, x_old, audio[:, ch]).astype(np.float32)
    return out


def _play_audio(audio: np.ndarray, sr: int) -> bool:
    """
    Tries sounddevice playback. Returns True if played, False otherwise.
    """
    try:
        import sounddevice as sd  # pip install sounddevice
        sd.play(audio, sr)
        sd.wait()
        return True
    except Exception:
        return False


def _write_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    import soundfile as sf
    sf.write(str(path), audio, sr)


# -------- Sequencer --------
@dataclass
class Voice:
    name: str
    sample: SampleMeta
    base_gain: float = 1.0


def pick_voice(
    lib,
    *,
    name: str,
    try_queries: list[dict[str, Any]],
) -> Voice:
    """
    Try multiple lib.get(...) queries in order and return the first that works.
    Each dict is passed into lib.get(...).
    """
    last_err: Optional[Exception] = None
    for q in try_queries:
        try:
            sample = lib.get(**q)
            return Voice(name=name, sample=sample, base_gain=1.0)
        except Exception as e:
            last_err = e

    # Helpful debug info
    kits = lib.list_kits()
    codes = lib.list_codes()[:60]
    raise FileNotFoundError(
        f"Could not pick voice '{name}'. Last error: {last_err}\n"
        f"Available kits (sample): {kits[:25]}{'...' if len(kits)>25 else ''}\n"
        f"Available codes (sample): {codes}{'...' if len(lib.list_codes())>60 else ''}"
    )

from pathlib import Path
from typing import Optional, Union

import numpy as np

# assumes you already have:
#   _read_audio(path) -> (audio[frames, channels], sr)
#   _resample_linear(audio, src_sr, dst_sr) -> audio_resampled
# and SoundMaster class available (from sound_master.py)


def play_voice(
    voice,
    sound_master: Optional["SoundMaster"] = None,
    sr: int = 44100,
    *,
    gain: float = 2,
    duration: Optional[float] = None,   # seconds; None = play full sample
    start_in: float = 0.0,              # seconds from now (only used with sound_master)
    fade_in: float = 0.005,
    fade_out: float = 0.010,
) -> Optional[int]:
    """
    Play a single voice/sample.

    If sound_master is provided:
      - the sound is mixed into the persistent stream (polyphonic, no cutoffs)
      - returns voice_id (int) so you can stop it later

    If sound_master is None:
      - falls back to sd.play() (this will cut off any previous sd.play)

    Accepts:
      - Voice (with .sample.path)
      - SampleMeta (with .path)
      - Path / str (path to audio file)
    """
    # Resolve path
    if hasattr(voice, "sample") and hasattr(voice.sample, "path"):
        path = Path(voice.sample.path)
    elif hasattr(voice, "path"):
        path = Path(voice.path)
    else:
        path = Path(voice)

    # If we have a SoundMaster, let it handle loading/resampling/mixing.
    # This is the recommended path for interactive playback.
    if sound_master is not None:
        # SoundMaster already resamples to its own sr. If you want to enforce sr,
        # instantiate SoundMaster(sr=sr).
        return sound_master.add(
            path,
            gain=gain,
            start_in=start_in,
            duration=duration,
            fade_in=fade_in,
            fade_out=fade_out,
        )

    # Otherwise: do the old one-shot behavior.
    import sounddevice as sd  # pip install sounddevice

    audio, src_sr = _read_audio(path)  # -> (frames, channels)
    audio = _resample_linear(audio, src_sr, sr)

    # Force stereo for playback
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)

    # Avoid blasting (simple normalization)
    peak = float(np.max(np.abs(audio)) + 1e-9)
    if peak > 1.0:
        audio = audio / peak

    audio = audio * float(gain)

    sd.play(audio, sr)
    return None

def render_pattern(
    voices: dict[str, Voice],
    pattern: dict[str, list[int]],
    *,
    bpm: float,
    sr: int = 44100,
    steps_per_bar: int = 16,
    bars: int = 2,
) -> np.ndarray:
    seconds_per_beat = 60.0 / bpm
    beats_per_bar = 4.0
    seconds_per_bar = beats_per_bar * seconds_per_beat
    step_len_sec = seconds_per_bar / steps_per_bar
    total_len_sec = seconds_per_bar * bars + 1.0  # +tail
    total_frames = int(math.ceil(total_len_sec * sr))

    mix = np.zeros((total_frames, 2), dtype=np.float32)

    # cache decoded audio per sample path
    cache: dict[Path, tuple[np.ndarray, int]] = {}

    def get_audio(meta: SampleMeta) -> np.ndarray:
        if meta.path not in cache:
            audio, src_sr = _read_audio(meta.path)
            audio = _resample_linear(audio, src_sr, sr)
            # force stereo
            if audio.shape[1] == 1:
                audio = np.repeat(audio, 2, axis=1)
            cache[meta.path] = (audio, sr)
        return cache[meta.path][0]

    for voice_name, steps in pattern.items():
        v = voices[voice_name]
        audio = get_audio(v.sample)

        for i, hit in enumerate(steps):
            if hit <= 0:
                continue

            t = i * step_len_sec
            start = int(round(t * sr))
            end = min(total_frames, start + audio.shape[0])
            if start >= total_frames:
                continue

            # simple velocity-to-gain mapping: hit is 1..10 (ish)
            gain = v.base_gain * (0.35 + 0.07 * min(hit, 10))

            mix[start:end, :] += gain * audio[: (end - start), :]

    # soft limiter to avoid clipping
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 1.0:
        mix /= peak

    return mix


def main():
    # CHANGE THIS to your actual samples root (folder containing china_18, kick_24, hihat_14, etc.)
    SAMPLES_ROOT = Path("Drum").expanduser()

    lib = DrumSampleLibrary(SAMPLES_ROOT, seed=42)

    # Auto-pick voices (these defaults match what appears in your tree: kick_24 with code "k",
    # snare sets with code "sn", and hihat_14 with "ht_*" like ht_chik etc.)
    kick = pick_voice(
        lib,
        name="kick",
        try_queries=[
            # Main kick set: kick_24/kick/kick/k_vl*_rr*.flac
            dict(
                kit="kick_24",
                articulation_contains="kick",
                code="k",
                prefer_mics=["kick", "oh"],  # leaf folder names seen under kick_24
                velocity=10,
                random_choice=True,
            ),

            # Other kick_24 variants: rc/sc/tc have codes like k_rc / k_sc / k_tc with cl/oh
            dict(
                kit="kick_24",
                articulation_contains="rc",
                code_prefix="k_rc",
                prefer_mics=["cl", "oh"],
                velocity=4,
                random_choice=True,
            ),
            dict(
                kit="kick_24",
                articulation_contains="sc",
                code_prefix="k_sc",
                prefer_mics=["cl", "oh"],
                velocity=4,
                random_choice=True,
            ),
            dict(
                kit="kick_24",
                articulation_contains="tc",
                code_prefix="k_tc",
                prefer_mics=["cl", "oh"],
                velocity=3,
                random_choice=True,
            ),

            # No-damp kick: kick_24_nodamp/.../k_nodamp_vl*_rr*.flac
            dict(
                kit="kick_24_nodamp",
                code_prefix="k_nodamp",
                prefer_mics=["kick", "oh"],
                velocity=4,
                random_choice=True,
            ),

            # Global fallbacks (if your root differs from the sample tree)
            dict(
                kit=None,
                code="k",
                prefer_mics=["kick", "cl", "oh"],
                random_choice=True,
            ),
            dict(
                kit=None,
                code_prefix="k_",
                prefer_mics=["kick", "cl", "oh"],
                random_choice=True,
            ),
        ],
    )

    snare = pick_voice(
        lib,
        name="snare",
        try_queries=[
            # If you have kits with plain sn_vl*_rr*.flac (e.g. 14d_basic, 14p_basic), this will work:
            dict(
                kit=None,
                code="sn",
                prefer_mics=["top", "oh", "btm", "out"],
                velocity=7,
                random_choice=True,
            ),

            # Your snare_14 uses codes like sn_bdig / sn_flutter, so match by prefix:
            dict(
                kit="snare_14",
                articulation_contains="edge",     # prefer the standard hit set
                code_prefix="sn_",
                prefer_mics=["top", "oh", "btm"],
                velocity=7,                       # maps to nearest available layer
                random_choice=True,
            ),

            # Final fallback: any snare_14 articulation with sn_ prefix
            dict(
                kit="snare_14",
                code_prefix="sn_",
                prefer_mics=["top", "oh", "btm"],
                random_choice=True,
            ),
        ],
    )

    hat = pick_voice(
        lib,
        name="hat",
        try_queries=[
            # Prefer the standard chick set: hihat_14/chik/(cl|oh)/ht_chik_vl*_rr*.flac
            dict(
                kit="hihat_14",
                articulation_contains="chik",
                code_prefix="ht_chik",
                prefer_mics=["cl", "oh"],
                velocity=5,
                random_choice=True,
            ),

            # Any hat in hihat_14 (covers other ht_* sets like ht_tc_s, etc.)
            dict(
                kit="hihat_14",
                code_prefix="ht_",
                prefer_mics=["cl", "oh"],
                velocity=5,
                random_choice=True,
            ),

            # Global fallback: any kit that has ht_* hats
            dict(
                kit=None,
                code_prefix="ht_",
                prefer_mics=["cl", "oh", "top", "btm"],
                random_choice=True,
            ),
        ],
    )

    voices = {"kick": kick, "snare": snare, "hat": hat}

    # 2 bars, 16 steps/bar (16th notes)
    # Values are "hit strength" (0 = no hit, 1..10 = louder)
    pattern = {
        "hat":   [6,0,5,0, 6,0,5,0, 6,0,5,0, 6,0,5,0] * 2,  # 8th-note hat, mild accents
        "kick":  [8,0,0,0, 0,0,0,0, 8,0,0,0, 0,0,3,0] * 2,  # kick on 1 and 3 + small pickup
        "snare": [0,0,0,0, 8,0,0,0, 0,0,0,0, 8,0,0,0] * 2,  # snare on 2 and 4
    }

    audio = render_pattern(voices, pattern, bpm=110, sr=44100, steps_per_bar=16, bars=2)

    played = _play_audio(audio, 44100)
    if not played:
        out = Path("beat_render.wav").resolve()
        _write_wav(out, audio, 44100)
        print(f"Could not play audio (no playback device?). Wrote: {out}")

    print("\nPicked samples:")
    for v in voices.values():
        print(f"- {v.name}: {v.sample.path} (kit={v.sample.kit}, art={v.sample.articulation}, mic={v.sample.mic}, code={v.sample.code})")


if __name__ == "__main__":
    main()