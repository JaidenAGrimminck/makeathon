import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union
from piano import PianoSampleLibrary

import numpy as np
import soundfile as sf
import sounddevice as sd


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


@dataclass
class _VoiceInstance:
    audio: np.ndarray          # (frames, channels) float32
    pos: int = 0               # current playback index
    gain: float = 1.0


class PolyphonicPlayer:
    """
    Persistent mixer stream. Call trigger(...) to layer sounds without cutting others off.
    """

    def __init__(self, sr: int = 44100, channels: int = 2, blocksize: int = 1024, limiter: bool = True):
        self.sr = sr
        self.channels = channels
        self.blocksize = blocksize
        self.limiter = limiter

        self._cache: Dict[Path, np.ndarray] = {}
        self._voices: List[_VoiceInstance] = []
        self._lock = threading.Lock()

        self._stream = sd.OutputStream(
            samplerate=self.sr,
            channels=self.channels,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def close(self):
        self._stream.stop()
        self._stream.close()

    def _load_audio(self, path: Path) -> np.ndarray:
        path = Path(path)
        if path in self._cache:
            return self._cache[path]

        audio, src_sr = sf.read(str(path), always_2d=True)
        audio = audio.astype(np.float32, copy=False)

        # resample if needed
        if src_sr != self.sr:
            audio = _resample_linear(audio, int(src_sr), self.sr)

        # force stereo/desired channels
        if audio.shape[1] == 1 and self.channels == 2:
            audio = np.repeat(audio, 2, axis=1)
        elif audio.shape[1] != self.channels:
            # simple downmix/upmix
            if audio.shape[1] > self.channels:
                audio = audio[:, :self.channels]
            else:
                audio = np.pad(audio, ((0, 0), (0, self.channels - audio.shape[1])), mode="constant")

        # tame insane peaks a bit
        peak = float(np.max(np.abs(audio)) + 1e-9)
        if peak > 1.5:
            audio = audio / peak

        self._cache[path] = audio
        return audio

    def trigger(self, src: Union[str, Path, np.ndarray], gain: float = 1.0):
        """
        Layer a new sound immediately.
        - src can be a file path or a preloaded numpy array (frames, channels)
        """
        if isinstance(src, np.ndarray):
            audio = src.astype(np.float32, copy=False)
        else:
            audio = self._load_audio(Path(src))

        with self._lock:
            self._voices.append(_VoiceInstance(audio=audio, pos=0, gain=float(gain)))

    def _callback(self, outdata, frames, time_info, status):
        out = np.zeros((frames, self.channels), dtype=np.float32)

        with self._lock:
            alive: List[_VoiceInstance] = []
            for v in self._voices:
                remain = v.audio.shape[0] - v.pos
                if remain <= 0:
                    continue
                n = min(frames, remain)
                out[:n, :] += v.audio[v.pos:v.pos + n, :] * v.gain
                v.pos += n
                if v.pos < v.audio.shape[0]:
                    alive.append(v)
            self._voices = alive

        # optional soft limiter to avoid clipping when stacking notes
        if self.limiter:
            out = np.tanh(out)

        outdata[:] = out


def main():
    import time
    piano = PianoSampleLibrary("Piano")
    player = PolyphonicPlayer(sr=44100)

    # Play a C major chord at once (won't cut off)
    for n in ["C4", "E4", "G4"]:
        player.trigger(piano.path(n, "H", closest=True), gain=0.6)

    # Another chord quickly after (previous tails still ring)
    time.sleep(1)
    for n in ["F4", "A4", "C5"]:
        player.trigger(piano.path(n, 0.8, closest=True), gain=0.6)

if __name__ == "__main__":
    main()