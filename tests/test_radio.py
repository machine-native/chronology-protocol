import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.radio import (fragment, parse_fragment, Reassembler, pow_valid,
                       airtime_estimate_s, MAGIC, HEADER_LEN, DEFAULT_MTU)


def real_block() -> bytes:
    """A genuine anchor block from the live chain capture, if present."""
    chain = ROOT / "live" / "chain-blocks.hex"
    if not chain.is_file():
        pytest.skip("no chain capture available")
    for line in chain.read_text().split():
        raw = bytes.fromhex(line)
        if len(raw) > 300:            # the CHRN anchor blocks are 306 bytes
            return raw
    pytest.skip("no suitable block")


def test_fragment_roundtrip_real_block():
    raw = real_block()
    frags = fragment(raw)
    assert all(len(f) <= DEFAULT_MTU for f in frags)
    assert all(f[:4] == MAGIC for f in frags)
    r = Reassembler()
    out = [r.feed(f) for f in frags]
    assert out[-1] == raw and all(o is None for o in out[:-1])
    assert pow_valid(raw)


def test_out_of_order_and_duplicate_fragments():
    raw = real_block()
    frags = fragment(raw)
    shuffled = frags[::-1] + frags          # reversed, then every fragment again
    r = Reassembler()
    delivered = [x for x in (r.feed(f) for f in shuffled) if x is not None]
    assert delivered == [raw]               # exactly once, despite duplicates


def test_lost_fragment_never_delivers_until_repeat():
    raw = real_block()
    frags = fragment(raw)
    if len(frags) < 2:
        pytest.skip("block fits in one fragment")
    r = Reassembler()
    for f in frags[1:]:                     # first fragment lost
        assert r.feed(f) is None
    assert r.pending()                      # still waiting
    assert r.feed(frags[0]) == raw          # the repeat completes it


def test_corrupted_payload_is_rejected_not_delivered():
    raw = real_block()
    frags = fragment(raw)
    bad = bytearray(frags[0])
    bad[HEADER_LEN + 5] ^= 0xFF             # flip a byte inside the header region
    r = Reassembler()
    for f in [bytes(bad)] + frags[1:]:
        r.feed(f)
    # nothing valid was produced, and the reassembler did not latch the id
    assert not r.seen


def test_forged_block_without_work_is_rejected():
    raw = bytearray(real_block())
    raw[76:80] = b"\x00\x00\x00\x00"        # destroy the nonce -> PoW fails
    forged = bytes(raw)
    assert not pow_valid(forged)
    r = Reassembler()
    for f in fragment(forged):
        assert r.feed(f) is None            # self-authentication does its job


def test_non_chrb_traffic_ignored():
    r = Reassembler()
    assert r.feed(b"hello world") is None
    assert r.feed(b"") is None
    assert parse_fragment(b"CHRB\x02" + b"\x00" * 6) is None   # wrong version


def test_airtime_is_plausible():
    raw = real_block()
    n = len(fragment(raw))
    t = airtime_estimate_s(n, sf=9)
    assert 0.1 < t < 30                     # seconds, not milliseconds or minutes
    assert airtime_estimate_s(n, sf=12) > airtime_estimate_s(n, sf=7)
