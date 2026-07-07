"""Smoke tests for the WER/CER/alignment module."""
from vad_bench.metrics import cer, normalize, wer, word_alignment


def test_normalize():
    assert normalize("  HELLO   world  ") == "hello world"
    assert normalize("") == ""
    assert normalize("½") == normalize("½")  # NFKC stable


def test_cer():
    assert cer("HELLO world", "hello  WORLD") == 0.0
    assert abs(cer("abc", "axc") - 1 / 3) < 1e-9
    assert cer("", "anything") == 1.0
    assert cer("anything", "") == 1.0


def test_wer():
    assert wer("the cat sat", "the cat sit") == 1 / 3
    assert wer("", "anything") == 1.0


def test_word_alignment_equal():
    parts = word_alignment("satu dua tiga", "satu dua tiga")
    assert all(p["kind"] == "equal" for p in parts)


def test_word_alignment_delete():
    parts = word_alignment("satu dua tiga", "satu tiga")
    kinds = [p["kind"] for p in parts]
    assert "equal" in kinds
    assert "delete" in kinds


def test_word_alignment_insert():
    parts = word_alignment("satu tiga", "satu dua tiga")
    kinds = [p["kind"] for p in parts]
    assert "insert" in kinds


def test_word_alignment_substitute():
    parts = word_alignment("satu dua", "satu tiga")
    kinds = [p["kind"] for p in parts]
    assert "substitute" in kinds


def test_word_alignment_empty():
    assert word_alignment("", "") == []
    assert all(p["kind"] == "insert" for p in word_alignment("", "hello"))
    assert all(p["kind"] == "delete" for p in word_alignment("hello", ""))