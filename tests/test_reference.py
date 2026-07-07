"""Reference transcript parsing."""
import json
from pathlib import Path

import pytest

from vad_bench.reference import load_reference


def test_load_reference(tmp_path, monkeypatch):
    # Build a fake transcript file and point REFERENCE_TXT at it.
    sample = (
        "# header\n"
        "# another header\n"
        "00:00:00.000 No text\n"
        "00:00:00.560 Hello world\n"
        "00:00:05.799 Second line here\n"
        "\n"
        "00:01:30.000 Outro\n"
    )
    fake = tmp_path / "transcript.txt"
    fake.write_text(sample, encoding="utf-8")
    monkeypatch.setattr("vad_bench.reference.REFERENCE_TXT", fake)

    joined, segs = load_reference()
    # Headers dropped, "No text" placeholder dropped, blank line dropped.
    assert joined == "hello world second line here outro", joined
    assert len(segs) == 3
    # End timestamps filled from next segment's start.
    assert segs[0].end_s == pytest.approx(5.799)
    assert segs[1].end_s == pytest.approx(90.000)
    assert segs[2].end_s is None


def test_load_reference_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("vad_bench.reference.REFERENCE_TXT", tmp_path / "nonexistent.txt")
    with pytest.raises(FileNotFoundError):
        load_reference()