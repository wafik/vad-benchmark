"""Reference cleaner.

Takes the tactiq/YouTube transcript export at ``data/text_podcast.txt`` and
produces two artifacts:

- ``joined_reference.txt``  — plain text used for WER/CER scoring.
- ``segments.json``         — list of ``(start_s, text)`` tuples, kept for the
                              optional VAD boundary-quality analysis (§9).

The cleaning rules match what the transcript exporter produces:
- Drop ``#`` comment header lines.
- Drop lines whose text (after timestamp) is exactly ``No text``.
- Strip the leading ``HH:MM:SS.mmm`` timestamp.
- Normalize: NFKC + lowercase + collapse whitespace + strip (same as
  ``metrics.normalize`` so scoring is fair).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .metrics import normalize
from .paths import REFERENCE_TXT

_TS_RE = re.compile(r"^\s*(\d+):(\d+):(\d+)[.,](\d+)\s+(.*)$")
_NOISE_TEXT = {"no text", ""}


@dataclass
class Segment:
    start_s: float
    end_s: float | None  # None if no following boundary
    text: str

    def to_dict(self) -> dict:
        return {"start_s": round(self.start_s, 3), "end_s": round(self.end_s, 3) if self.end_s is not None else None,
                "text": self.text}


def _parse_timestamp(m: re.Match) -> float:
    """Parse the (h, m, s, ms) capture groups of ``_TS_RE`` into seconds.

    The regex has 5 capture groups: (h, m, s, ms, text) — take the first 4.
    """
    h, m, s, ms, _ = m.groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def load_reference() -> tuple[str, list[Segment]]:
    """Return ``(joined_text_normalized, segments)``.

    Raises FileNotFoundError if the source transcript is absent.
    """
    if not REFERENCE_TXT.exists():
        raise FileNotFoundError(
            f"missing reference transcript: {REFERENCE_TXT}"
        )

    raw_segments: list[Segment] = []
    for line in REFERENCE_TXT.read_text(encoding="utf-8").splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = _TS_RE.match(line)
        if not m:
            continue
        text = m.group(5).strip()
        if text.lower() in _NOISE_TEXT:
            continue
        start = _parse_timestamp(m)
        raw_segments.append(Segment(start_s=start, end_s=None, text=text))

    # Fill end timestamps with the next segment's start (matches YouTube's
    # "this line begins at T" semantic; the line's effective window is
    # [start, next_start)).
    for i, seg in enumerate(raw_segments):
        if i + 1 < len(raw_segments):
            seg.end_s = raw_segments[i + 1].start_s

    joined = " ".join(s.text for s in raw_segments)
    joined_norm = normalize(joined)
    return joined_norm, raw_segments


def write_reference_artifacts(out_dir: Path) -> tuple[Path, Path]:
    """Write ``reference.txt`` (joined) and ``segments.json`` (per-line)."""
    joined, segments = load_reference()
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / "reference.txt"
    seg_path = out_dir / "segments.json"
    txt_path.write_text(joined, encoding="utf-8")
    import json
    seg_path.write_text(
        json.dumps([s.to_dict() for s in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return txt_path, seg_path