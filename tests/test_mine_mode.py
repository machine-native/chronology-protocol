"""Tests for FPGA mine mode and the block submitter.

The submitter is the last gate before a block goes to every peer on the chain,
and a chain does not forget. So its refusals are tested against a REAL block
from the live chain -- one this project actually mined -- and against deliberate
corruptions of it. A gate that has only ever been shown to pass is not a gate.

No test here contacts the network. `--check-only` exists so that the validation
path can be exercised without the send path.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.bitcoin_jan09 import block_hash, target_from_bits

CHAIN = ROOT / "live" / "chain-blocks.hex"
SUBMIT = ROOT / "scripts" / "submit_block.py"


def _a_real_block():
    """The lowest-height block on the chain that carries real proof-of-work."""
    if not CHAIN.is_file():
        pytest.skip("live/chain-blocks.hex not present")
    for line in CHAIN.read_text().split():
        raw = bytes.fromhex(line.strip())
        if len(raw) > 80:
            return raw
    pytest.skip("no blocks in chain file")


def _record(raw: bytes, **overrides):
    rec = {
        "height": 221,
        "hash": block_hash(raw[:80]),
        "nonce": int.from_bytes(raw[76:80], "little"),
        "raw_block_hex": raw.hex(),
    }
    rec.update(overrides)
    return rec


def _run(tmp_path, rec):
    p = tmp_path / "block.json"
    p.write_text(json.dumps(rec))
    return subprocess.run([sys.executable, str(SUBMIT), str(p), "--check-only"],
                          capture_output=True, text=True)


def test_accepts_a_real_block_from_the_chain(tmp_path):
    """A block the chain already accepted must pass the submitter's own checks."""
    raw = _a_real_block()
    r = _run(tmp_path, _record(raw))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "pow       VALID" in r.stdout
    assert "nothing was sent" in r.stdout


def test_refuses_a_block_whose_pow_is_broken(tmp_path):
    """Flip the nonce and the proof-of-work must fail -- this is the real gate."""
    raw = bytearray(_a_real_block())
    raw[76] ^= 0xFF                       # corrupt the nonce
    raw = bytes(raw)
    # The record's stated hash is recomputed, so this is a *self-consistent*
    # file with genuinely invalid work -- exactly what a miner bug would produce.
    r = _run(tmp_path, _record(raw))
    assert r.returncode != 0
    assert "proof-of-work is not valid" in (r.stdout + r.stderr)


def test_refuses_a_file_that_contradicts_its_own_bytes(tmp_path):
    """A stated hash that does not match the raw block means the file is wrong.

    Caught before the PoW check, because a file that disagrees with itself
    cannot be reasoned about at all -- whichever half is true, something that
    wrote it was broken.
    """
    raw = _a_real_block()
    r = _run(tmp_path, _record(raw, hash="00" * 32))
    assert r.returncode != 0
    assert "inconsistent" in (r.stdout + r.stderr)


def test_refuses_garbage_that_is_not_a_block(tmp_path):
    r = _run(tmp_path, {"hash": "00" * 32, "raw_block_hex": "deadbeef"})
    assert r.returncode != 0


def test_mine_does_not_submit_without_the_flag():
    """--submit must be opt-in. Its absence is the difference between a local
    file and an irreversible broadcast, so it is asserted rather than assumed."""
    src = (ROOT / "scripts" / "fpga_host.py").read_text()
    assert '"--submit", action="store_true"' in src
    assert "if not a.submit:" in src, "mine must check the flag before broadcasting"
    # The submit path must not be reachable when the flag is absent: the guard
    # returns before it.
    guard = src.index("if not a.submit:")
    call = src.index("from ctp.p2p_v01 import submit_block", guard)
    assert "return" in src[guard:call], "the no-submit branch must return, not fall through"


def test_the_coarse_filter_is_not_trusted_as_the_target_test():
    """At difficulty 1 the FPGA's zero-word filter admits ~1 in 65,536 hashes
    that are still above target, so the host's exact check is load-bearing."""
    target = target_from_bits(0x1D00FFFF)
    assert target < (1 << 224), "filter accepts hashes below 2^224"
    false_positive_band = ((1 << 224) - target) / (1 << 224)
    assert false_positive_band > 1e-5, false_positive_band
    src = (ROOT / "scripts" / "fpga_host.py").read_text()
    assert "int(block_hash(raw[:80]), 16) > target" in src, (
        "mine must re-check every candidate against the exact target; the "
        "FPGA's filter is not the consensus rule"
    )
