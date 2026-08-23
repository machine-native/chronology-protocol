"""Tests for the rolling-code optical session.

Two implementations must agree byte-for-byte or the evidence is worthless: the
JavaScript in tools/rolling-code.html, which produces the code a camera records,
and scripts/rolling_code.py, which a verifier uses to say what should have been
visible. If they drift, every photograph taken in between becomes unverifiable
and there is no way to tell from the frames themselves.

So the formula is pinned here in a third place, written out longhand from the
specification rather than by calling either implementation.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.sandwich import challenge

HTML = ROOT / "tools" / "rolling-code.html"
STARTER = ROOT / "scripts" / "start_optical_session.py"


def _longhand(seed16: str, slot: int) -> str:
    """The specification, implemented here so a shared bug cannot hide."""
    return hashlib.sha256(f"CHRN-ROLL/v1:{seed16}:{slot}".encode()).hexdigest()[:12].upper()


def test_python_reference_matches_the_specification():
    seed = "D2B79B45D60F408A"
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "rolling_code.py"), "expected", seed,
         "2026-08-20T15:20:00", "2026-08-20T15:20:19", "--slot", "10"],
        capture_output=True, text=True, check=True).stdout
    for slot in (178723920, 178723921):
        assert _longhand(seed, slot) in out, f"slot {slot} disagrees with the spec"


def test_html_uses_the_same_formula_and_length():
    """The page's JS must derive the same string; drift here is silent and fatal."""
    src = HTML.read_text(encoding="utf-8")
    assert '"CHRN-ROLL/v1:"+seed+":"+slot' in src, "domain or ordering changed"
    assert ".slice(0,12).toUpperCase()" in src, "code length or case changed"
    assert "Math.floor(now/slotSec)" in src, "slot derivation changed"


def test_seed_is_the_first_16_hex_of_the_challenge():
    """SEED16 binds the photographs to B0. If it were independent of the
    challenge, the frames would prove nothing about when they were taken."""
    ch_path = ROOT / "live" / "g2b-work" / "challenge.json"
    if not ch_path.is_file():
        pytest.skip("no reference session present")
    ch = json.loads(ch_path.read_text())
    q = challenge(ch["b0_hash"], bytes.fromhex(ch["session_id"]))
    assert q.hex() == ch["challenge"], "challenge is not reproducible from B0"
    assert len(q.hex()[:16]) == 16
    src = STARTER.read_text(encoding="utf-8")
    assert 'seed16 = q.hex()[:16].upper()' in src, (
        "the session starter must derive the seed from the challenge, not "
        "generate an independent one"
    )


def test_starter_refuses_to_overwrite_an_open_session(tmp_path):
    """A challenge fixes a session's lower bound. Replacing it would silently
    invalidate photographs already taken against the old one."""
    work = tmp_path / "session"
    work.mkdir()
    (work / "challenge.json").write_text("{}")
    r = subprocess.run(
        [sys.executable, str(STARTER), "--work", str(work)],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "Refusing to overwrite" in (r.stdout + r.stderr)


def test_codes_differ_between_adjacent_slots():
    """The whole upgrade over a single handwritten code: frames taken seconds
    apart must show visibly different codes, or they evidence one instant."""
    seed = "D2B79B45D60F408A"
    codes = [_longhand(seed, s) for s in range(178723920, 178723926)]
    assert len(set(codes)) == len(codes), "codes repeat across adjacent slots"
