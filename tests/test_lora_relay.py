"""Tests for the RYLR998 LoRa driver.

Everything here runs without a radio. What is testable offline is the part that
would otherwise fail silently on air: whether a fragment fits inside the
module's AT command limit, whether hex survives the round trip, and whether a
block that arrives in pieces reassembles into exactly the block that was sent.

A fragment one byte too long does not raise -- the module simply truncates the
command and transmits a corrupt frame, which the receiver then drops as failing
proof-of-work. The symptom is "nothing ever arrives", which is the least
informative failure available. So the size arithmetic is pinned here.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from ctp.radio import fragment, Reassembler, pow_valid, HEADER_LEN
from ctp.bitcoin_jan09 import block_hash

import lora_relay

CHAIN = ROOT / "live" / "chain-blocks.hex"


def _real_block() -> bytes:
    if not CHAIN.is_file():
        pytest.skip("live/chain-blocks.hex not present")
    return bytes.fromhex(CHAIN.read_text().split()[297].strip())   # height 298


def test_every_fragment_fits_the_modules_at_command_limit():
    """AT+SEND accepts 240 ASCII characters. Hex doubles a fragment's size."""
    raw = _real_block()
    for i, f in enumerate(fragment(raw, mtu=lora_relay.LORA_MTU)):
        ascii_len = len(f.hex())
        assert ascii_len <= lora_relay.RYLR_MAX_ASCII, (
            f"fragment {i} is {ascii_len} ASCII chars after hex encoding, over "
            f"the module's {lora_relay.RYLR_MAX_ASCII} limit. The module would "
            f"truncate the command and transmit a corrupt frame."
        )


def test_the_mtu_is_derived_from_the_limit_not_guessed():
    assert lora_relay.LORA_MTU * 2 <= lora_relay.RYLR_MAX_ASCII
    assert lora_relay.LORA_MTU > HEADER_LEN, "no room for payload"


def test_a_real_block_survives_fragmentation_and_reassembly():
    """The whole point: what goes out must be what comes back."""
    raw = _real_block()
    frames = fragment(raw, mtu=lora_relay.LORA_MTU)
    assert len(frames) > 1, "a 306-byte block should need several fragments"

    asm = Reassembler()
    out = None
    for f in frames:
        # simulate the wire: hex out, hex back in, exactly as AT+SEND / +RCV do
        out = asm.feed(bytes.fromhex(f.hex().upper()), validate=pow_valid)
    assert out == raw
    assert block_hash(out[:80]) == block_hash(raw[:80])


def test_a_missing_fragment_yields_nothing_rather_than_a_wrong_block():
    """Silence is the correct failure. A partial block must never be emitted."""
    raw = _real_block()
    frames = fragment(raw, mtu=lora_relay.LORA_MTU)
    asm = Reassembler()
    for f in frames[:-1]:                      # drop the last one
        assert asm.feed(f, validate=pow_valid) is None
    assert asm.pending(), "the reassembler should still be waiting"


def test_a_corrupted_fragment_is_rejected_by_proof_of_work():
    """This is why the link needs no authentication: work is the authentication."""
    raw = bytearray(_real_block())
    raw[76] ^= 0xFF                            # break the nonce
    asm = Reassembler()
    out = None
    for f in fragment(bytes(raw), mtu=lora_relay.LORA_MTU):
        out = asm.feed(f, validate=pow_valid)
    assert out is None, "a block failing proof-of-work must not be delivered"


def test_fragments_out_of_order_still_reassemble():
    """LoRa gives no ordering guarantee, and repeats arrive interleaved."""
    raw = _real_block()
    frames = fragment(raw, mtu=lora_relay.LORA_MTU)
    asm = Reassembler()
    out = None
    for f in reversed(frames):
        out = asm.feed(f, validate=pow_valid)
    assert out == raw


def test_a_repeated_transmission_is_not_delivered_twice():
    """--repeat sends the whole block several times; the receiver must dedupe."""
    raw = _real_block()
    frames = fragment(raw, mtu=lora_relay.LORA_MTU)
    asm = Reassembler()
    first = [asm.feed(f, validate=pow_valid) for f in frames]
    second = [asm.feed(f, validate=pow_valid) for f in frames]
    assert any(x == raw for x in first)
    assert all(x is None for x in second), "the same block was delivered twice"
