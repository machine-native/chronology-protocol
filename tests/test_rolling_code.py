import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rolling_code import code_for


def test_pinned_vectors_match_the_html_implementation():
    # These four values were derived independently by the pure-JS SHA-256 inside
    # tools/rolling-code.html (run under node) and by this Python implementation,
    # and matched byte-for-byte on 2026-08-21. If either side changes, a phone
    # displaying codes and a verifier recomputing them would silently disagree —
    # so these are pinned.
    seed = "D2B79B45D60F408A"
    assert code_for(seed, 0) == "13CF0187C37C"
    assert code_for(seed, 1) == "1F3505C96554"
    assert code_for(seed, 178731600) == "F044AEC9CAB2"
    assert code_for(seed, 999999999) == "F6270744BC79"


def test_seed_validation():
    with pytest.raises(ValueError):
        code_for("short", 0)
    with pytest.raises(ValueError):
        code_for("G" * 16, 0)                 # not hex
    assert code_for("d2b79b45d60f408a", 5) == code_for("D2B79B45D60F408A", 5)


def test_adjacent_slots_differ():
    seed = "0123456789ABCDEF"
    codes = {code_for(seed, s) for s in range(1000, 1050)}
    assert len(codes) == 50
