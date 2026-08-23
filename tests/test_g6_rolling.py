"""Tests for the epoch-4 rolling-code assessment.

The rolling code exists to prove a photographic series spans real elapsed time,
not merely that it happened after B0. A single handwritten code already proved
the latter; if a series shows only one or two codes it has added almost nothing,
and the consolidation must say so rather than producing a checkpoint that looks
as strong as a good series.

These tests use synthetic EXIF times. No photographs are needed, which is the
point -- the thresholds are checkable before anyone goes outside.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from rolling_code import code_for
from run_g6 import MIN_FRAMES, MIN_SLOTS, MIN_SPAN_S, assess, rolling_expectation

SEED = "E97C458B5C5E5E7D"


def series(offsets_s, base=1787000000, slot=10):
    """Synthetic frames at the given second offsets."""
    exif_ns = {f"{i:05d}.jpg": (base + o) * 10**9 for i, o in enumerate(offsets_s)}
    rows = rolling_expectation(exif_ns, SEED, slot)
    span = max(offsets_s) - min(offsets_s)
    return rows, assess(rows, span)


def test_expected_codes_match_the_reference_implementation():
    """The consolidation must derive the same code the phone displayed."""
    rows, _ = series([0, 15, 30, 45, 60, 75])
    for r in rows:
        assert r["expected_code"] == code_for(SEED, r["slot"])


def test_a_good_series_passes():
    rows, v = series([0, 15, 30, 45, 60, 75, 90])
    assert v["meets_min_frames"] and v["meets_min_span"] and v["meets_min_slots"]
    assert v["distinct_codes"] == v["distinct_slots"]


def test_the_actual_rehearsal_series_is_rejected():
    """The real indoor rehearsal: 6 frames, 29 seconds. Frames were taken at
    +0,4,10,21,27,29 seconds. It covers 4 slots but spans under a minute."""
    rows, v = series([0, 4, 10, 21, 27, 29])
    assert v["frames"] == 6
    assert v["span_seconds"] == 29
    assert v["meets_min_frames"]
    assert not v["meets_min_span"], "29s must not satisfy a 60s requirement"


def test_a_burst_of_frames_in_one_slot_is_rejected():
    """Ten frames in four seconds is one instant photographed ten times. It
    passes a naive frame count and proves nothing about elapsed time."""
    rows, v = series([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
    assert v["frames"] == 10
    assert v["meets_min_frames"]
    assert v["distinct_slots"] == 1
    assert not v["meets_min_slots"]
    assert not v["meets_min_span"]


def test_two_frames_far_apart_is_rejected_despite_a_long_span():
    """A long span with almost no frames is not a series; it is two photographs.
    Span alone must not be sufficient."""
    rows, v = series([0, 600])
    assert v["meets_min_span"]
    assert not v["meets_min_frames"]


def test_distinct_codes_track_distinct_slots():
    """If two frames share a slot they must show the same code -- otherwise the
    verifier's expectation would disagree with the photograph."""
    rows, v = series([0, 1, 2, 30, 60, 90])
    by_slot = {}
    for r in rows:
        by_slot.setdefault(r["slot"], set()).add(r["expected_code"])
    for slot, codes in by_slot.items():
        assert len(codes) == 1, f"slot {slot} produced more than one code"


def test_thresholds_are_all_enforced_independently():
    """Each threshold must be able to fail on its own; a single combined check
    would let a weak series pass by being strong in the wrong dimension."""
    _, weak_span = series([0, 1, 2, 3, 4, 5])
    _, weak_count = series([0, 100])
    assert not weak_span["meets_min_span"] and weak_span["meets_min_frames"]
    assert weak_count["meets_min_span"] and not weak_count["meets_min_frames"]
    assert (MIN_FRAMES, MIN_SPAN_S, MIN_SLOTS) == (6, 60, 4)
