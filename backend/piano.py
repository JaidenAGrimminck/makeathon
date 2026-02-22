from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union

VelocityLayer = Literal["L", "H"]

# Filenames look like:
#   A0vH.flac, C3vL.flac, D#4vH.flac, F#7vL.flac
# Based on your structure. :contentReference[oaicite:4]{index=4} :contentReference[oaicite:5]{index=5}
_FILENAME_RE = re.compile(r"^(?P<n>[A-Ga-g])(?P<acc>#|b)?(?P<oct>-?\d+)v(?P<vel>[HL])$", re.IGNORECASE)

_PITCHCLASS = {
    "C": 0,  "C#": 1,  "DB": 1,
    "D": 2,  "D#": 3,  "EB": 3,
    "E": 4,
    "F": 5,  "F#": 6,  "GB": 6,
    "G": 7,  "G#": 8,  "AB": 8,
    "A": 9,  "A#": 10, "BB": 10,
    "B": 11,
}

_PC_TO_NAME = {
    0: "C", 1: "C#", 2: "D", 3: "D#", 4: "E", 5: "F",
    6: "F#", 7: "G", 8: "G#", 9: "A", 10: "A#", 11: "B"
}


@dataclass(frozen=True)
class PianoSample:
    path: Path
    note: str           # canonical, e.g. "D#4"
    midi: int           # MIDI note number
    layer: VelocityLayer  # "L" or "H"
    ext: str            # ".flac", ".wav", ...


class PianoSampleLibrary:
    """
    Simple index + query for a piano sample folder where files are named:
        <NOTE><OCTAVE>v<L|H>.<ext>
    e.g. A0vH.flac, D#4vL.flac. :contentReference[oaicite:6]{index=6} :contentReference[oaicite:7]{index=7}

    Key features:
      - get(note="C4", velocity="H")
      - get(note=60, velocity=0.2)   # MIDI note + float velocity -> L/H
      - closest=True fallback if a note doesn't exist in the set
      - helpful listing methods
    """

    def __init__(
        self,
        root_dir: Union[str, Path],
        exts: Tuple[str, ...] = (".flac", ".wav", ".aif", ".aiff"),
    ) -> None:
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.exts = tuple(e.lower() for e in exts)

        self._samples: List[PianoSample] = []
        self._by_note: Dict[str, Dict[VelocityLayer, PianoSample]] = {}
        self._by_midi: Dict[int, Dict[VelocityLayer, PianoSample]] = {}

        self._scan()

    # ---------- Public API ----------

    def list_notes(self) -> List[str]:
        """All available notes sorted by MIDI."""
        notes = {s.note for s in self._samples}
        return sorted(notes, key=lambda n: self.note_to_midi(n))

    def list_midis(self) -> List[int]:
        return sorted({s.midi for s in self._samples})

    def available_layers(self, note: Union[str, int]) -> List[VelocityLayer]:
        midi = note if isinstance(note, int) else self.note_to_midi(note)
        layers = self._by_midi.get(midi, {})
        return sorted(layers.keys())

    def get(
        self,
        note: Union[str, int],
        velocity: Union[VelocityLayer, str, float, int, None] = None,
        *,
        closest: bool = False,
        prefer: VelocityLayer = "H",
    ) -> PianoSample:
        """
        Fetch a sample.
          - note: "C4" / "D#3" / "Eb3" or MIDI int
          - velocity:
              * "H"/"L" or "high"/"low"
              * float 0..1 (>=0.5 -> H else L)
              * int 0..127 (>=64 -> H else L)
              * None -> prefer 'prefer' if available, else whichever exists
          - closest: if note not available, choose nearest available MIDI note
        """
        target_midi = note if isinstance(note, int) else self.note_to_midi(note)

        midi = target_midi
        if midi not in self._by_midi:
            if not closest:
                raise FileNotFoundError(self._missing_note_msg(target_midi))
            midi = self._nearest_midi(target_midi)

        layer = self._normalize_velocity(velocity, prefer=prefer)

        # pick layer if available; else fall back to any available layer for that note
        layers = self._by_midi[midi]
        if layer in layers:
            return layers[layer]

        # fallback order: prefer -> other
        if prefer in layers:
            return layers[prefer]
        # last resort: whichever exists
        return next(iter(layers.values()))

    def path(
        self,
        note: Union[str, int],
        velocity: Union[VelocityLayer, str, float, int, None] = None,
        *,
        closest: bool = False,
        prefer: VelocityLayer = "H",
    ) -> Path:
        return self.get(note, velocity, closest=closest, prefer=prefer).path

    # Optional convenience: playback (same deps as your beat script)
    def play(self, note: Union[str, int], velocity: Union[VelocityLayer, str, float, int, None] = None, *, sr: int = 44100, closest: bool = False) -> None:
        """
        Plays the selected piano sample using soundfile + sounddevice.
        pip install soundfile sounddevice
        """
        import numpy as np
        import soundfile as sf
        import sounddevice as sd

        p = self.path(note, velocity, closest=closest)
        audio, src_sr = sf.read(str(p), always_2d=True)
        audio = audio.astype("float32", copy=False)

        # very simple linear resample if needed
        if src_sr != sr:
            x_old = np.linspace(0.0, 1.0, num=audio.shape[0], endpoint=True)
            new_len = int(round(audio.shape[0] * (sr / src_sr)))
            x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=True)
            out = np.zeros((new_len, audio.shape[1]), dtype="float32")
            for ch in range(audio.shape[1]):
                out[:, ch] = np.interp(x_new, x_old, audio[:, ch]).astype("float32")
            audio = out

        # force stereo
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)

        # tame peaks
        peak = float((abs(audio)).max() + 1e-9)
        if peak > 1.0:
            audio = audio / peak
        audio *= 0.9

        sd.play(audio, sr)
        sd.wait()

    # ---------- Internals ----------

    def _scan(self) -> None:
        if not self.root_dir.exists():
            raise FileNotFoundError(f"Root dir does not exist: {self.root_dir}")

        for dirpath, _dirnames, filenames in os.walk(self.root_dir):
            # Your structure is a single directory with files. :contentReference[oaicite:8]{index=8}
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() not in self.exts:
                    continue
                meta = self._parse_file(p)
                if meta:
                    self._samples.append(meta)
                    self._by_note.setdefault(meta.note, {})[meta.layer] = meta
                    self._by_midi.setdefault(meta.midi, {})[meta.layer] = meta

        if not self._samples:
            raise FileNotFoundError(f"No audio files found under {self.root_dir} with {self.exts}")

    def _parse_file(self, path: Path) -> Optional[PianoSample]:
        m = _FILENAME_RE.match(path.stem)
        if not m:
            return None

        n = m.group("n").upper()
        acc = (m.group("acc") or "").upper()
        octv = int(m.group("oct"))
        layer: VelocityLayer = m.group("vel").upper()  # "L" or "H"

        # Canonicalize flats to sharps for internal note representation
        note_name = f"{n}{acc}".replace("B", "B").upper()
        if acc == "B":  # flat
            # Convert flat note to equivalent pitch class then to sharp name
            pc = _PITCHCLASS[f"{n}B"]
            note_base = _PC_TO_NAME[pc]
        else:
            pc = _PITCHCLASS.get(f"{n}{acc}", None)
            if pc is None:
                return None
            note_base = _PC_TO_NAME[pc]

        midi = (octv + 1) * 12 + pc
        note = f"{note_base}{octv}"

        return PianoSample(
            path=path,
            note=note,
            midi=midi,
            layer=layer,
            ext=path.suffix.lower(),
        )

    @staticmethod
    def _normalize_velocity(v, *, prefer: VelocityLayer) -> VelocityLayer:
        if v is None:
            return prefer
        if isinstance(v, str):
            vv = v.strip().upper()
            if vv in ("H", "HIGH"):
                return "H"
            if vv in ("L", "LOW"):
                return "L"
            raise ValueError(f"Unknown velocity string: {v!r} (use 'H'/'L' or float 0..1)")
        if isinstance(v, (float, int)):
            if isinstance(v, float):
                return "H" if v >= 0.5 else "L"
            # int: treat as MIDI velocity 0..127
            return "H" if int(v) >= 64 else "L"
        raise ValueError(f"Unsupported velocity type: {type(v)}")

    @staticmethod
    def note_to_midi(note: str) -> int:
        # supports "Eb3" or "D#3" etc
        note = note.strip().upper()
        m = re.match(r"^([A-G])(#|B)?(-?\d+)$", note)
        if not m:
            raise ValueError(f"Bad note format: {note!r} (expected like C4, D#3, Eb3)")

        n = m.group(1)
        acc = m.group(2) or ""
        octv = int(m.group(3))

        key = f"{n}{acc}"
        if key not in _PITCHCLASS:
            raise ValueError(f"Unsupported pitch: {key} (use # or b)")
        pc = _PITCHCLASS[key]
        return (octv + 1) * 12 + pc

    def _nearest_midi(self, target: int) -> int:
        midis = self.list_midis()
        return min(midis, key=lambda m: abs(m - target))

    def _missing_note_msg(self, target_midi: int) -> str:
        # give the user the closest few notes
        midis = self.list_midis()
        midis_sorted = sorted(midis, key=lambda m: abs(m - target_midi))
        near = midis_sorted[:6]
        near_notes = [self._midi_to_note(m) for m in near]
        return (
            f"No piano sample for MIDI {target_midi}. "
            f"Try closest=True or choose one of: {near_notes}"
        )

    @staticmethod
    def _midi_to_note(midi: int) -> str:
        pc = midi % 12
        octv = (midi // 12) - 1
        return f"{_PC_TO_NAME[pc]}{octv}"
    