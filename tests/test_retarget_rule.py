# SPDX-License-Identifier: Apache-2.0
"""The retarget rule is tested before the retarget, not debugged during it.

`live/capture_retarget.py` re-implements `GetNextWorkRequired` from the released
2009 source so that the published first-retarget prediction can be judged by
arithmetic rather than by eye. That re-implementation fires exactly once, on one
block, months after it was written -- which is the worst possible moment to find
out it was wrong.

So the rule is exercised here on synthetic headers that make each branch happen:
the non-boundary early return, the off-by-one walk-back, both timespan bounds, and
the proof-of-work-limit clamp that the prediction actually turns on.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from capture_retarget import (  # noqa: E402
    N_INTERVAL, N_TARGET_TIMESPAN, PROOF_OF_WORK_LIMIT_BITS,
    bits_to_target, target_to_bits, next_work_required,
)

LIMIT = 0x1D00FFFF


def _chain(n, spacing_s, bits=LIMIT, t0=1_785_781_375):
    """Headers indexed BY HEIGHT: index 0 is the genesis, index h is height h."""
    return [{"nTime": t0 + i * spacing_s, "nBits": bits, "hash": f"{i:064x}"}
            for i in range(0, n + 1)]


def test_compact_round_trip():
    t = bits_to_target(LIMIT)
    assert target_to_bits(t) == LIMIT
    # the published difficulty-1 target, as a sanity anchor
    assert t == 0xFFFF << (8 * (0x1D - 3))


def test_no_retarget_off_the_boundary():
    h = _chain(500, 600)
    bits, detail = next_work_required(h, 499)
    assert detail["retarget"] is False
    assert bits == LIMIT, "nBits must be carried forward untouched off a boundary"


def test_boundary_is_height_2015():
    """(height+1) % 2016 == 0 first holds at 2015, setting nBits for 2016."""
    h = _chain(N_INTERVAL, 600)
    _, off = next_work_required(h, N_INTERVAL - 2)
    assert off["retarget"] is False
    _, on = next_work_required(h, N_INTERVAL - 1)
    assert on["retarget"] is True
    assert on["last_height"] == N_INTERVAL - 1


def test_walk_back_is_2015_intervals_not_2016():
    """The 2009 off-by-one: the span covers nInterval-1 gaps."""
    spacing = 600
    h = _chain(N_INTERVAL, spacing)
    _, d = next_work_required(h, N_INTERVAL - 1)
    assert d["first_height"] == 0, "the walk-back from 2015 lands on the genesis"
    assert d["nActualTimespan"] == (N_INTERVAL - 1) * spacing, (
        "the span must be nTime(2015) - nTime(0): 2015 intervals, not 2016")


def test_slow_chain_clamps_to_the_proof_of_work_limit():
    """This is the case the published prediction rests on.

    The laboratory chain has always mined slower than ten minutes, so the ratio
    pushes the target UP -- but it already sits at the limit, so it is clamped
    straight back and nBits does not move.
    """
    h = _chain(N_INTERVAL, 3600)          # an hour a block: six times slower
    bits, d = next_work_required(h, N_INTERVAL - 1)
    assert d["bounds_applied"] is True, "a 6x-slow chain must hit the 4x upper bound"
    assert d["nActualTimespan_after_bounds"] == N_TARGET_TIMESPAN * 4
    assert d["clamped_to_proof_of_work_limit"] is True
    assert bits == PROOF_OF_WORK_LIMIT_BITS, (
        "difficulty is already at its floor; the retarget must change nothing")


def test_fast_chain_would_raise_difficulty():
    """The negative control: the clamp is not simply always returning the limit."""
    h = _chain(N_INTERVAL, 60)            # a minute a block: ten times faster
    bits, d = next_work_required(h, N_INTERVAL - 1)
    assert d["clamped_to_proof_of_work_limit"] is False
    assert bits_to_target(bits) < bits_to_target(LIMIT), (
        "a fast chain must produce a SMALLER target, i.e. higher difficulty -- "
        "if this ever passes trivially the clamp test above proves nothing")


def test_lower_bound_applies_too():
    h = _chain(N_INTERVAL, 1)
    _, d = next_work_required(h, N_INTERVAL - 1)
    assert d["nActualTimespan_after_bounds"] == N_TARGET_TIMESPAN // 4
