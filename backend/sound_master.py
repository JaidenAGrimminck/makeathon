from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np
import sounddevice as sd
import soundfile as sf


def _resample_linear(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Simple linear resampler (good enough for one-shots)."""
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
    """Force audio to desired channel count."""
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.shape[1] == channels:
        return audio
    if audio.shape[1] == 1 and channels == 2:
        return np.repeat(audio, 2, axis=1)
    if audio.shape[1] > channels:
        return audio[:, :channels]
    # upmix by padding zeros
    return np.pad(audio, ((0, 0), (0, channels - audio.shape[1])), mode="constant")


@dataclass
class _Voice:
    voice_id: int
    audio: np.ndarray             # float32 (frames, channels)
    start_frame: int              # absolute timeline frame to start
    end_frame: Optional[int]      # absolute timeline frame to end (exclusive). None => until sample ends
    gain: float
    loop: bool
    fade_in_frames: int
    fade_out_frames: int


class SoundMaster:
    """
    Persistent audio mixer.

    - add(path/array, duration=..., start_in=...) to layer audio
    - no cutoffs when triggering frequently (polyphony)
    - optional soft limiter to prevent harsh clipping
    """

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

        # timeline cursor (frames rendered so far)
        self._cursor = 0

        self._stream = sd.OutputStream(
            samplerate=self.sr,
            channels=self.channels,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def close(self) -> None:
        """Stop audio output cleanly."""
        try:
            self._stream.stop()
        finally:
            self._stream.close()

    # ---------- Public API ----------

    def add(
        self,
        src: Union[str, Path, np.ndarray],
        *,
        gain: float = 1.0,
        start_in: float = 0.0,          # seconds from now
        duration: Optional[float] = None,  # seconds to play (cut with fade out)
        loop: bool = False,             # if True and duration is set, loop for that duration
        fade_in: float = 0.005,         # seconds
        fade_out: float = 0.010,        # seconds
    ) -> int:
        """
        Add audio to the mix. Returns a voice_id you can later stop().

        src:
          - file path (wav/flac/aiff) or
          - numpy array (frames, channels) float-ish
        """
        audio = self._load_audio(src)

        gain = float(gain)
        start_in_frames = int(round(float(start_in) * self.sr))
        fade_in_frames = int(round(float(fade_in) * self.sr))
        fade_out_frames = int(round(float(fade_out) * self.sr))

        with self._lock:
            voice_id = self._next_id
            self._next_id += 1

            start_frame = self._cursor + max(0, start_in_frames)

            if duration is None:
                end_frame = None
            else:
                end_frame = start_frame + int(round(float(duration) * self.sr))

            self._voices[voice_id] = _Voice(
                voice_id=voice_id,
                audio=audio,
                start_frame=start_frame,
                end_frame=end_frame,
                gain=gain,
                loop=bool(loop),
                fade_in_frames=max(0, fade_in_frames),
                fade_out_frames=max(0, fade_out_frames),
            )

        return voice_id

    def stop(self, voice_id: int, *, fade_out: float = 0.010) -> None:
        """Stop a specific voice soon (optionally with a short fade)."""
        fade_frames = int(round(float(fade_out) * self.sr))
        with self._lock:
            v = self._voices.get(voice_id)
            if not v:
                return
            end_now = self._cursor + max(0, fade_frames)
            if v.end_frame is None or end_now < v.end_frame:
                v.end_frame = end_now
                v.fade_out_frames = max(v.fade_out_frames, fade_frames)
                self._voices[voice_id] = v

    def clear(self, *, fade_out: float = 0.010) -> None:
        """Stop everything."""
        fade_frames = int(round(float(fade_out) * self.sr))
        with self._lock:
            end_now = self._cursor + max(0, fade_frames)
            for vid, v in list(self._voices.items()):
                if v.end_frame is None or end_now < v.end_frame:
                    v.end_frame = end_now
                    v.fade_out_frames = max(v.fade_out_frames, fade_frames)
                    self._voices[vid] = v

    # ---------- Internals ----------

    def _load_audio(self, src: Union[str, Path, np.ndarray]) -> np.ndarray:
        if isinstance(src, np.ndarray):
            audio = src.astype(np.float32, copy=False)
            audio = _force_channels(audio, self.channels)
            return audio

        path = Path(src).expanduser().resolve()
        if self.cache_files and path in self._cache:
            return self._cache[path]

        audio, src_sr = sf.read(str(path), always_2d=True)
        audio = audio.astype(np.float32, copy=False)

        if int(src_sr) != self.sr:
            audio = _resample_linear(audio, int(src_sr), self.sr)

        audio = _force_channels(audio, self.channels)

        # tame extreme peaks
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

        dead_ids = []

        for v in voices:
            # not started yet
            if block_end <= v.start_frame:
                continue

            # already ended
            if v.end_frame is not None and block_start >= v.end_frame:
                dead_ids.append(v.voice_id)
                continue

            # Determine active region in this block
            active_start = max(block_start, v.start_frame)
            active_end = block_end

            # If duration-limited, clamp
            if v.end_frame is not None:
                active_end = min(active_end, v.end_frame)

            if active_end <= active_start:
                continue

            out_off = active_start - block_start
            n = active_end - active_start

            # position into voice timeline (frames since start)
            rel = active_start - v.start_frame

            # For non-looped playback, clamp to sample length
            if not v.loop:
                if rel >= v.audio.shape[0]:
                    dead_ids.append(v.voice_id)
                    continue
                n = min(n, v.audio.shape[0] - rel)
                if n <= 0:
                    dead_ids.append(v.voice_id)
                    continue

                chunk = v.audio[rel:rel + n]
                env = self._envelope(v, rel, n)
                mix[out_off:out_off + n] += chunk * (v.gain * env)

                # if we reached sample end and no explicit end_frame, mark dead
                if v.end_frame is None and (rel + n) >= v.audio.shape[0]:
                    dead_ids.append(v.voice_id)
            else:
                # looped playback: may wrap within this chunk
                L = v.audio.shape[0]
                if L <= 0:
                    dead_ids.append(v.voice_id)
                    continue
                rel_mod = rel % L

                remaining = n
                write_pos = out_off
                read_pos = rel_mod

                while remaining > 0:
                    take = min(remaining, L - read_pos)
                    chunk = v.audio[read_pos:read_pos + take]
                    env = self._envelope(v, rel + (n - remaining), take)
                    mix[write_pos:write_pos + take] += chunk * (v.gain * env)

                    remaining -= take
                    write_pos += take
                    read_pos = 0

                # if duration-limited looping ended, mark dead
                if v.end_frame is not None and active_end >= v.end_frame:
                    dead_ids.append(v.voice_id)

        # master gain + optional limiter
        mix *= self.master_gain
        if self.limiter:
            mix = np.tanh(mix)

        outdata[:] = mix

        # advance cursor and cleanup dead voices
        self._cursor += frames
        if dead_ids:
            with self._lock:
                for vid in dead_ids:
                    self._voices.pop(vid, None)

    def _envelope(self, v: _Voice, rel_start: int, n: int) -> np.ndarray:
        """
        Returns (n,1) envelope for fade in/out.
        rel_start is frames since voice start.
        """
        env = np.ones((n, 1), dtype=np.float32)

        # fade in
        fi = v.fade_in_frames
        if fi > 0:
            a = rel_start
            b = rel_start + n
            if a < fi:
                # portion intersects fade-in window
                i0 = 0
                i1 = min(n, fi - a)
                ramp = (np.arange(a, a + i1, dtype=np.float32) / fi).reshape(-1, 1)
                env[i0:i1] *= ramp

        # fade out (only if we have an end_frame)
        if v.end_frame is not None and v.fade_out_frames > 0:
            fo = v.fade_out_frames
            # frames remaining until end for each sample in this chunk
            # voice ends at rel_end_total = end_frame - start_frame
            rel_end_total = v.end_frame - v.start_frame
            idx = np.arange(rel_start, rel_start + n, dtype=np.int32)
            remaining = rel_end_total - idx  # how many frames left (including current)
            mask = remaining <= fo
            if np.any(mask):
                # ramp from 1 -> 0 over fo frames
                # remaining==fo => near 1, remaining==0 => 0
                ramp = (remaining.astype(np.float32) / fo).clip(0.0, 1.0).reshape(-1, 1)
                env *= np.where(mask.reshape(-1, 1), ramp, 1.0)

        return env
    
if __name__ == "__main__":
    import time
    from piano import PianoSampleLibrary  # the one we made earlier

    piano = PianoSampleLibrary("Piano")
    sm = SoundMaster(sr=44100, channels=2, master_gain=1.0, limiter=True)

    # Play a chord (2 seconds), then quickly add notes on top
    sm.add(piano.path("C4", "H", closest=True), gain=0.5, duration=2.0)
    sm.add(piano.path("E4", "H", closest=True), gain=0.5, duration=2.0)
    sm.add(piano.path("G4", "H", closest=True), gain=0.5, duration=2.0)

    time.sleep(0.2)
    sm.add(piano.path("A4", 0.8, closest=True), gain=0.7, duration=0.6)
    time.sleep(0.15)
    sm.add(piano.path("G4", 0.7, closest=True), gain=0.7, duration=0.6)

    time.sleep(3.0)
    sm.close()