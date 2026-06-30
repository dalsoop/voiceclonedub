"""Cue cleaning (Whisper de-hallucination) and sentence-level merging."""

from voiceclonedub import merge


def test_collapse_intra_cue_repetition():
    assert merge._collapse_rep("A. A. A.") == "A."
    assert merge._collapse_rep("A. B.") == "A. B."


def test_clean_cues_drops_adjacent_duplicate():
    cues = [
        {"start_ms": 0, "end_ms": 1000, "text": "the same line here"},
        {"start_ms": 1000, "end_ms": 2000, "text": "the same line here"},  # hallucinated repeat
        {"start_ms": 2000, "end_ms": 3000, "text": "something different"},
    ]
    out = merge.clean_cues(cues)
    assert len(out) == 2
    assert out[0]["end_ms"] == 2000  # window extended over the dropped duplicate
    assert out[1]["text"] == "something different"


def test_clean_cues_keeps_distinct_lines():
    cues = [
        {"start_ms": 0, "end_ms": 1000, "text": "alpha"},
        {"start_ms": 1000, "end_ms": 2000, "text": "beta"},
    ]
    assert len(merge.clean_cues(cues)) == 2


def test_merge_preserves_original_timing():
    cues = [
        {"start_ms": 0, "end_ms": 800, "text": "Hello there."},
        {"start_ms": 900, "end_ms": 1700, "text": "How are you?"},
    ]
    out = merge.merge(cues)
    assert out[0]["start_ms"] == 0
    assert out[-1]["end_ms"] == 1700


def test_merge_empty_input():
    assert merge.merge([]) == []
