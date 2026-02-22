# sound_master.py
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np
import sounddevice as sd
import soundfile as sf


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


def _force_channels(audio: np.ndarray, channels: int) -> np.ndarray:
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.shape[1] == channels:
        return audio
    if audio.shape[1] == 1 and channels == 2:
        return np.repeat(audio, 2, axis=1)
    if audio.shape[1] > channels:
        return audio[:, :channels]
    return np.pad(audio, ((0, 0), (0, channels - audio.shape[1])), mode="constant")


@dataclass
class _Voice:
    voice_id: int
    audio: np.ndarray
    start_frame: int
    end_frame: Optional[int]
    gain: float
    loop: bool
    fade_in_frames: int
    fade_out_frames: int

    # --- Modulation params ---
    pan: float = 0.0                 # -1..+1 (L..R)
    rate: float = 1.0                # playback rate (pitch/speed)
    lp_cutoff: Optional[float] = None  # Hz
    hp_cutoff: Optional[float] = None  # Hz
    tremolo_rate: float = 0.0        # Hz
    tremolo_depth: float = 0.0       # 0..1

    # --- DSP state ---
    lp_state: Optional[np.ndarray] = None   # (channels,)
    hp_state: Optional[np.ndarray] = None   # (channels,)
    tremolo_phase: float = 0.0              # radians


class SoundMaster:
    def __init__(
        self,
        sr: int = 44100,
        channels: int = 2,
        blocksize: int = 1024,
        master_gain: float = 1.0,
        limiter: bool = True,
        cache_files: bool = True,
    ):
        self.sr = int(sr)
        self.channels = int(channels)
        self.blocksize = int(blocksize)
        self.master_gain = float(master_gain)
        self.limiter = bool(limiter)
        self.cache_files = bool(cache_files)

        self._lock = threading.Lock()
        self._cache: Dict[Path, np.ndarray] = {}
        self._voices: Dict[int, _Voice] = {}
        self._next_id = 1
        self._cursor = 0  # absolute output frames rendered so far
        self._global_rate = 1.0  # global pitch/rate multiplier

        self._stream = sd.OutputStream(
            samplerate=self.sr,
            channels=self.channels,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def close(self) -> None:
        try:
            self._stream.stop()
        finally:
            self._stream.close()

    def get_ids(self) -> Dict[int, _Voice]:
        with self._lock:
            return dict(self._voices)

    # ---------- Add / Stop / Clear ----------

    def add(
        self,
        src: Union[str, Path, np.ndarray],
        *,
        gain: float = 1.0,
        start_in: float = 0.0,
        duration: Optional[float] = None,
        loop: bool = False,
        fade_in: float = 0.005,
        fade_out: float = 0.010,

        # FX/modulation initial values:
        pan: float = 0.0,
        rate: float = 1.0,
        lp_cutoff: Optional[float] = None,
        hp_cutoff: Optional[float] = None,
        tremolo_rate: float = 0.0,
        tremolo_depth: float = 0.0,
    ) -> int:
        audio = self._load_audio(src)

        start_in_frames = int(round(float(start_in) * self.sr))
        fade_in_frames = int(round(float(fade_in) * self.sr))
        fade_out_frames = int(round(float(fade_out) * self.sr))

        with self._lock:
            voice_id = self._next_id
            self._next_id += 1

            start_frame = self._cursor + max(0, start_in_frames)
            end_frame = None if duration is None else start_frame + int(round(float(duration) * self.sr))

            v = _Voice(
                voice_id=voice_id,
                audio=audio,
                start_frame=start_frame,
                end_frame=end_frame,
                gain=float(gain),
                loop=bool(loop),
                fade_in_frames=max(0, fade_in_frames),
                fade_out_frames=max(0, fade_out_frames),
                pan=float(pan),
                rate=float(rate),
                lp_cutoff=lp_cutoff,
                hp_cutoff=hp_cutoff,
                tremolo_rate=float(tremolo_rate),
                tremolo_depth=float(tremolo_depth),
                lp_state=np.zeros((self.channels,), dtype=np.float32),
                hp_state=np.zeros((self.channels,), dtype=np.float32),
                tremolo_phase=0.0,
            )
            self._voices[voice_id] = v

        return voice_id

    def stop(self, voice_id: int, *, fade_out: float = 0.010) -> None:
        fade_frames = int(round(float(fade_out) * self.sr))
        with self._lock:
            v = self._voices.get(voice_id)
            if not v:
                return
            end_now = self._cursor + max(0, fade_frames)
            if v.end_frame is None or end_now < v.end_frame:
                v.end_frame = end_now
                v.fade_out_frames = max(v.fade_out_frames, fade_frames)

    def clear(self, *, fade_out: float = 0.010) -> None:
        fade_frames = int(round(float(fade_out) * self.sr))
        with self._lock:
            end_now = self._cursor + max(0, fade_frames)
            for v in self._voices.values():
                if v.end_frame is None or end_now < v.end_frame:
                    v.end_frame = end_now
                    v.fade_out_frames = max(v.fade_out_frames, fade_frames)

    # ---------- Global modulation ----------

    def set_global_rate(self, rate: float) -> None:
        """Set a global playback rate multiplier applied to all voices (0.01x..4x typical)."""
        with self._lock:
            self._global_rate = max(0.01, float(rate))

    def set_master_gain(self, gain: float) -> None:
        """Set master output gain multiplier (0.. about 4 typical)."""
        with self._lock:
            self.master_gain = max(0.0, float(gain))

    # ---------- NEW: Modulate an active voice ----------

    def modulate(
        self,
        voice_id: int,
        *,
        gain: Optional[float] = None,
        pan: Optional[float] = None,
        rate: Optional[float] = None,
        lp_cutoff: Optional[float] = None,   # pass None to disable
        hp_cutoff: Optional[float] = None,   # pass None to disable
        tremolo_rate: Optional[float] = None,
        tremolo_depth: Optional[float] = None,
    ) -> None:
        """
        Update modulation parameters for a currently playing voice.
        """
        with self._lock:
            v = self._voices.get(voice_id)
            if not v:
                return
            if gain is not None:
                v.gain = float(gain)
            if pan is not None:
                v.pan = float(pan)
            if rate is not None:
                v.rate = max(0.01, float(rate))
            if lp_cutoff is not None or lp_cutoff is None:
                v.lp_cutoff = lp_cutoff
            if hp_cutoff is not None or hp_cutoff is None:
                v.hp_cutoff = hp_cutoff
            if tremolo_rate is not None:
                v.tremolo_rate = float(tremolo_rate)
            if tremolo_depth is not None:
                v.tremolo_depth = float(tremolo_depth)

    # ---------- Internals ----------

    def _load_audio(self, src: Union[str, Path, np.ndarray]) -> np.ndarray:
        if isinstance(src, np.ndarray):
            audio = src.astype(np.float32, copy=False)
            return _force_channels(audio, self.channels)

        path = Path(src).expanduser().resolve()
        if self.cache_files and path in self._cache:
            return self._cache[path]

        audio, src_sr = sf.read(str(path), always_2d=True)
        audio = audio.astype(np.float32, copy=False)
        if int(src_sr) != self.sr:
            audio = _resample_linear(audio, int(src_sr), self.sr)

        audio = _force_channels(audio, self.channels)

        peak = float(np.max(np.abs(audio)) + 1e-9)
        if peak > 2.0:
            audio = audio / peak

        if self.cache_files:
            self._cache[path] = audio
        return audio

    def _callback(self, outdata, frames, time_info, status):
        block_start = self._cursor
        block_end = self._cursor + frames

        mix = np.zeros((frames, self.channels), dtype=np.float32)

        with self._lock:
            voices = list(self._voices.values())
            global_rate = float(self._global_rate)

        dead_ids = []

        for v in voices:
            if block_end <= v.start_frame:
                continue

            if v.end_frame is not None and block_start >= v.end_frame:
                dead_ids.append(v.voice_id)
                continue

            active_start = max(block_start, v.start_frame)
            active_end = block_end
            if v.end_frame is not None:
                active_end = min(active_end, v.end_frame)

            if active_end <= active_start:
                continue

            out_off = active_start - block_start
            n = active_end - active_start

            # Output-relative frames since voice start
            rel = active_start - v.start_frame

            # --- RATE (sampler-style pitch/speed) ---
            rate = max(0.01, float(v.rate) * global_rate)
            L = v.audio.shape[0]
            if L <= 1:
                dead_ids.append(v.voice_id)
                continue

            pos0 = rel * rate
            if not v.loop:
                if pos0 >= L:
                    dead_ids.append(v.voice_id)
                    continue
                # clamp n so we don't read past sample end
                max_out = int(np.floor((L - 1 - pos0) / rate)) + 1
                if max_out <= 0:
                    dead_ids.append(v.voice_id)
                    continue
                n = min(n, max_out)
                if n <= 0:
                    continue

            # sample positions in input
            pos = pos0 + rate * np.arange(n, dtype=np.float32)
            if v.loop:
                pos = np.mod(pos, float(L))

            i0 = pos.astype(np.int64)
            frac = (pos - i0).astype(np.float32)
            i1 = i0 + 1

            if v.loop:
                i0 %= L
                i1 %= L
            else:
                i0 = np.clip(i0, 0, L - 1)
                i1 = np.clip(i1, 0, L - 1)

            a0 = v.audio[i0]  # (n, ch)
            a1 = v.audio[i1]
            chunk = a0 * (1.0 - frac)[:, None] + a1 * frac[:, None]

            # --- Envelope (fade-in/out) ---
            env = self._envelope(v, rel, n)  # (n,1)
            chunk = chunk * env

            # --- Pan (DJ-style) ---
            if self.channels == 2:
                p = float(np.clip(v.pan, -1.0, 1.0))
                ang = (p + 1.0) * (np.pi / 4.0)  # equal-power
                gl = np.cos(ang)
                gr = np.sin(ang)
                chunk[:, 0] *= gl
                chunk[:, 1] *= gr

            # --- Tremolo (AM) ---
            if v.tremolo_depth > 0.0 and v.tremolo_rate > 0.0:
                depth = float(np.clip(v.tremolo_depth, 0.0, 1.0))
                w = 2.0 * np.pi * float(v.tremolo_rate) / self.sr
                phases = v.tremolo_phase + w * np.arange(n, dtype=np.float32)
                amp = (1.0 - depth) + depth * (0.5 * (1.0 + np.sin(phases)))
                chunk *= amp[:, None]
                v.tremolo_phase = float((v.tremolo_phase + w * n) % (2.0 * np.pi))

            # --- Filters (DJ sweep) ---
            # High-pass first (if set), then low-pass (if set) => band-ish if both.
            if v.hp_cutoff is not None:
                chunk, v.hp_state = self._onepole_highpass(chunk, float(v.hp_cutoff), v.hp_state)
            if v.lp_cutoff is not None:
                chunk, v.lp_state = self._onepole_lowpass(chunk, float(v.lp_cutoff), v.lp_state)

            # --- Gain ---
            chunk *= float(v.gain)

            mix[out_off:out_off + n] += chunk

            # If we ended because we hit sample end and no explicit end_frame, kill it
            if (not v.loop) and v.end_frame is None:
                pos_last = pos0 + rate * (n - 1)
                if pos_last >= (L - 1):
                    dead_ids.append(v.voice_id)

        mix *= self.master_gain
        if self.limiter:
            mix = np.tanh(mix)

        outdata[:] = mix

        self._cursor += frames
        if dead_ids:
            with self._lock:
                for vid in dead_ids:
                    self._voices.pop(vid, None)

    def _envelope(self, v: _Voice, rel_start: int, n: int) -> np.ndarray:
        env = np.ones((n, 1), dtype=np.float32)

        fi = v.fade_in_frames
        if fi > 0:
            a = rel_start
            if a < fi:
                i1 = min(n, fi - a)
                ramp = (np.arange(a, a + i1, dtype=np.float32) / fi).reshape(-1, 1)
                env[:i1] *= ramp

        if v.end_frame is not None and v.fade_out_frames > 0:
            fo = v.fade_out_frames
            rel_end_total = v.end_frame - v.start_frame
            idx = np.arange(rel_start, rel_start + n, dtype=np.int32)
            remaining = rel_end_total - idx
            mask = remaining <= fo
            if np.any(mask):
                ramp = (remaining.astype(np.float32) / fo).clip(0.0, 1.0).reshape(-1, 1)
                env *= np.where(mask.reshape(-1, 1), ramp, 1.0)

        return env

    def _alpha(self, cutoff_hz: float) -> float:
        cutoff_hz = float(np.clip(cutoff_hz, 5.0, 0.49 * self.sr))
        return float(1.0 - np.exp(-2.0 * np.pi * cutoff_hz / self.sr))

    def _onepole_lowpass(self, x: np.ndarray, cutoff_hz: float, state: np.ndarray):
        a = self._alpha(cutoff_hz)
        y = np.empty_like(x)
        s = state.astype(np.float32, copy=False)
        for i in range(x.shape[0]):
            s += a * (x[i] - s)
            y[i] = s
        return y, s.copy()

    def _onepole_highpass(self, x: np.ndarray, cutoff_hz: float, state: np.ndarray):
        # HP = input - LP(input)
        lp, new_state = self._onepole_lowpass(x, cutoff_hz, state)
        return x - lp, new_state