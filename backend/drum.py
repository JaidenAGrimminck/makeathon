from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


# Filenames typically look like:
#   sn_vl3_rr2.flac
#   sn_rims_vl2_rr4.flac
#   cn_choke_rr3.flac
#   sn_flutter_rr1.wav
#
# We'll parse:
#   code = everything before _vlN and/or _rrN
#   velocity = N from _vlN (optional)
#   rr = N from _rrN (optional)
_FILENAME_RE = re.compile(
    r"^(?P<code>.+?)"
    r"(?:_(?P<layerkind>vl|dl)(?P<layer>\d+))?"
    r"(?:_rr(?P<rr>\d+))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SampleMeta:
    path: Path
    kit: str                     # first folder under root (e.g. "china_18", "kick_24", "14a_basic")
    articulation: Optional[str]   # everything between kit and leaf folder, joined with "/"
    mic: Optional[str]            # leaf folder that directly contains the file (e.g. "cl", "oh", "top", "btm", "kick")
    code: str                     # parsed from filename (e.g. "sn", "sn_rims", "cn_b", "k", "ht_chik")
    velocity: Optional[int]       # from _vlN (optional)
    rr: Optional[int]             # from _rrN (optional)
    ext: str                      # ".flac", ".wav", ...


class DrumSampleLibrary:
    """
    Indexes a folder of drum samples and lets you select samples by:
      - kit (top-level folder)
      - articulation (path between kit and leaf folder)
      - mic/position (leaf folder)
      - code (prefix in filename)
      - velocity layer (_vlN) and round-robin (_rrN)

    Folder mapping (based on your structure):
      root/kit/(articulation...)/leaf_folder/files...
    Examples:
      root/china_18/brush/cl/cn_b_vl1_rr1.flac
      root/hihat_14/chik/oh/ht_chik_vl2_rr3.flac
      root/14a_basic/top/sn_vl4_rr2.flac
      root/kick_24/kick/kick/k_vl3_rr1.flac
    """

    def __init__(
        self,
        root_dir: str | Path,
        exts: Sequence[str] = (".wav", ".flac", ".aif", ".aiff"),
        seed: Optional[int] = None,
    ) -> None:
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.exts = tuple(e.lower() for e in exts)
        self._rng = random.Random(seed)
        self._samples: list[SampleMeta] = []
        self._by_kit: dict[str, list[SampleMeta]] = {}
        self._scan()

    # ---------- Public helpers ----------

    def list_kits(self) -> list[str]:
        return sorted(self._by_kit.keys())

    def list_articulations(self, kit: str) -> list[str]:
        arts = {s.articulation for s in self._by_kit.get(kit, []) if s.articulation}
        return sorted(arts)

    def list_mics(self, kit: str, articulation: Optional[str] = None) -> list[str]:
        items = self._by_kit.get(kit, [])
        if articulation is not None:
            items = [s for s in items if s.articulation == articulation]
        mics = {s.mic for s in items if s.mic}
        return sorted(mics)

    def list_codes(
        self,
        kit: Optional[str] = None,
        articulation: Optional[str] = None,
        mic: Optional[str] = None,
    ) -> list[str]:
        items = self._iter_candidates(kit=kit, articulation=articulation, mic=mic)
        return sorted({s.code for s in items})

    # ---------- Core query ----------

    def find(
        self,
        *,
        kit: Optional[str] = None,
        articulation: Optional[str] = None,
        articulation_contains: Optional[str] = None,
        mic: Optional[str] = None,
        mic_in: Optional[Sequence[str]] = None,
        code: Optional[str] = None,
        code_prefix: Optional[str] = None,
        velocity: Optional[int] = None,
        rr: Optional[int] = None,
        exts: Optional[Sequence[str]] = None,
    ) -> list[SampleMeta]:
        """
        Returns all matching SampleMeta entries.
        """
        items = list(
            self._iter_candidates(
                kit=kit,
                articulation=articulation,
                articulation_contains=articulation_contains,
                mic=mic,
                mic_in=mic_in,
                code=code,
                code_prefix=code_prefix,
                exts=exts,
            )
        )

        # Velocity: choose nearest available velocity layer among candidates (if any have velocity)
        if velocity is not None:
            with_vel = [s for s in items if s.velocity is not None]
            if with_vel:
                vels = sorted({s.velocity for s in with_vel if s.velocity is not None})
                target = min(vels, key=lambda v: abs(v - velocity))
                items = [s for s in with_vel if s.velocity == target]

        # Round robin: exact filter if requested
        if rr is not None:
            items = [s for s in items if s.rr == rr]

        return items

    def get(
        self,
        *,
        kit: Optional[str] = None,
        articulation: Optional[str] = None,
        articulation_contains: Optional[str] = None,
        mic: Optional[str] = None,
        mic_in: Optional[Sequence[str]] = None,
        code: Optional[str] = None,
        code_prefix: Optional[str] = None,
        velocity: Optional[int] = None,
        rr: Optional[int] = None,
        exts: Optional[Sequence[str]] = None,
        prefer_mics: Optional[Sequence[str]] = None,
        random_choice: bool = True,
    ) -> SampleMeta:
        """
        Returns one matching SampleMeta (random by default).
        - If prefer_mics is provided, we'll try them in order.
        """
        if prefer_mics:
            for m in prefer_mics:
                hits = self.find(
                    kit=kit,
                    articulation=articulation,
                    articulation_contains=articulation_contains,
                    mic=m,
                    code=code,
                    code_prefix=code_prefix,
                    velocity=velocity,
                    rr=rr,
                    exts=exts,
                )
                if hits:
                    return self._pick(hits, random_choice=random_choice)

        hits = self.find(
            kit=kit,
            articulation=articulation,
            articulation_contains=articulation_contains,
            mic=mic,
            mic_in=mic_in,
            code=code,
            code_prefix=code_prefix,
            velocity=velocity,
            rr=rr,
            exts=exts,
        )
        if not hits:
            raise FileNotFoundError(
                "No samples match query. Try loosening filters (kit/articulation/mic/code)."
            )
        return self._pick(hits, random_choice=random_choice)

    # ---------- Internal ----------

    def _pick(self, hits: list[SampleMeta], *, random_choice: bool) -> SampleMeta:
        return self._rng.choice(hits) if random_choice else sorted(hits, key=lambda s: str(s.path))[0]

    def _iter_candidates(
        self,
        *,
        kit: Optional[str] = None,
        articulation: Optional[str] = None,
        articulation_contains: Optional[str] = None,
        mic: Optional[str] = None,
        mic_in: Optional[Sequence[str]] = None,
        code: Optional[str] = None,
        code_prefix: Optional[str] = None,
        exts: Optional[Sequence[str]] = None,
    ) -> Iterable[SampleMeta]:
        if kit is None:
            items = self._samples
        else:
            items = self._by_kit.get(kit, [])

        if articulation is not None:
            items = [s for s in items if s.articulation == articulation]
        elif articulation_contains is not None:
            items = [s for s in items if s.articulation and articulation_contains in s.articulation]

        if mic is not None:
            items = [s for s in items if s.mic == mic]
        elif mic_in is not None:
            mic_set = set(mic_in)
            items = [s for s in items if s.mic in mic_set]

        if code is not None:
            items = [s for s in items if s.code == code]
        elif code_prefix is not None:
            items = [s for s in items if s.code.startswith(code_prefix)]

        if exts is not None:
            allowed = set(e.lower() for e in exts)
            items = [s for s in items if s.ext.lower() in allowed]

        return items

    def _scan(self) -> None:
        if not self.root_dir.exists():
            raise FileNotFoundError(f"Root dir does not exist: {self.root_dir}")

        for dirpath, _dirnames, filenames in os.walk(self.root_dir):
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() not in self.exts:
                    continue
                meta = self._parse_sample_path(p)
                if meta:
                    self._samples.append(meta)
                    self._by_kit.setdefault(meta.kit, []).append(meta)

    def _parse_sample_path(self, abs_path: Path) -> Optional[SampleMeta]:
        try:
            rel = abs_path.relative_to(self.root_dir)
        except ValueError:
            return None

        parts = rel.parts
        if len(parts) < 2:
            return None  # need at least kit/file

        kit = parts[0]
        folder_parts = list(parts[1:-1])  # everything between kit and file
        if folder_parts:
            mic = folder_parts[-1]
            articulation = "/".join(folder_parts[:-1]) if len(folder_parts) > 1 else None
        else:
            mic = None
            articulation = None

        stem = abs_path.stem
        m = _FILENAME_RE.match(stem)
        if not m:
            # If a filename doesn't match, still index it as "code=stem"
            code = stem
            velocity = None
            rr = None
        else:
            code = m.group("code")
            velocity = int(m.group("layer")) if m.group("layerkind") and m.group("layer") else None
            rr = int(m.group("rr")) if m.group("rr") else None

        return SampleMeta(
            path=abs_path,
            kit=kit,
            articulation=articulation,
            mic=mic,
            code=code,
            velocity=velocity,
            rr=rr,
            ext=abs_path.suffix.lower(),
        )