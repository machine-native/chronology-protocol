"""Block relay over a low-bandwidth broadcast link (CHRN radio profile v1).

The point of this profile is a distribution path that does not depend on the
internet: anchor-chain blocks are small (306 bytes for a CHRN anchor block), so
they fit comfortably over LoRa or an amateur data mode.

The design is deliberately trivial, because proof-of-work makes it possible to be
trivial:

  **A block is self-authenticating.** Its hash must meet its own difficulty target
  and it must name its parent. A receiver therefore does not need to trust the
  transmitter, does not need a signature, and does not need a session. Forging a
  block costs the same work as mining one, so there is nothing to gain by lying,
  and a corrupted fragment simply fails to reassemble into something valid.

  Consequently: no encryption (the data is public), no authentication (the work
  is the authentication), no handshake, no retransmission negotiation. The sender
  broadcasts; anyone who hears enough fragments reconstructs and validates
  locally. Redundancy is achieved by repeating the whole transmission, which
  costs nothing but airtime and needs no back-channel — appropriate for a
  one-way, licence-exempt, possibly receive-only audience.

Wire format, one fragment (fits inside a 255-byte LoRa payload):

    magic   4 bytes   b"CHRB"
    version 1 byte    0x01
    id      4 bytes   first 4 bytes of the block's double-SHA256 (identifies the
                      transmission; NOT a security property, only a demultiplexer)
    index   1 byte    fragment number, 0-based
    count   1 byte    total fragments in this block
    payload n bytes   raw block bytes for this fragment
                      (total header = 11 bytes)

Reassembly keeps fragments by id, and once all `count` fragments are present it
concatenates them and hands the result to the caller's validator. Any of it can
be wrong — the validator is what decides.
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field

from .bitcoin_jan09 import dsha, block_hash, target_from_bits

MAGIC = b"CHRB"
VERSION = 1
HEADER_LEN = 11
DEFAULT_MTU = 255           # LoRa SF7-SF12 max application payload
MAX_FRAGMENTS = 255


def fragment(raw_block: bytes, mtu: int = DEFAULT_MTU) -> list[bytes]:
    """Split a raw block into broadcast fragments."""
    if not raw_block:
        raise ValueError("empty block")
    body = mtu - HEADER_LEN
    if body <= 0:
        raise ValueError("mtu too small for header")
    chunks = [raw_block[i:i + body] for i in range(0, len(raw_block), body)]
    if len(chunks) > MAX_FRAGMENTS:
        raise ValueError(f"block needs {len(chunks)} fragments, max {MAX_FRAGMENTS}")
    ident = dsha(raw_block[:80])[:4]
    out = []
    for i, chunk in enumerate(chunks):
        out.append(MAGIC + bytes([VERSION]) + ident + bytes([i, len(chunks)]) + chunk)
    return out


def parse_fragment(packet: bytes):
    """Return (id, index, count, payload) or None if this is not a CHRB fragment."""
    if len(packet) < HEADER_LEN or packet[:4] != MAGIC or packet[4] != VERSION:
        return None
    ident = packet[5:9]
    index, count = packet[9], packet[10]
    if count == 0 or index >= count:
        return None
    return ident, index, count, packet[HEADER_LEN:]


@dataclass
class Reassembler:
    """Collects fragments and emits complete blocks that pass proof-of-work.

    `validate` decides what is acceptable; the default checks only that the block
    hashes below its own stated target, which is the self-authenticating property.
    A node would pass a stricter validator that also checks the parent link.
    """
    partial: dict = field(default_factory=dict)
    seen: set = field(default_factory=set)

    def feed(self, packet: bytes, validate=None):
        parsed = parse_fragment(packet)
        if parsed is None:
            return None
        ident, index, count, payload = parsed
        if ident in self.seen:
            return None                      # already delivered this transmission
        slot = self.partial.setdefault(ident, {"count": count, "parts": {}})
        if slot["count"] != count:           # inconsistent claim: restart this id
            self.partial[ident] = slot = {"count": count, "parts": {}}
        slot["parts"][index] = payload
        if len(slot["parts"]) != count:
            return None
        raw = b"".join(slot["parts"][i] for i in range(count))
        del self.partial[ident]
        check = validate or pow_valid
        if not check(raw):
            return None                      # corrupt or forged: drop, stay open
        self.seen.add(ident)
        return raw

    def pending(self) -> dict:
        return {ident.hex(): (len(s["parts"]), s["count"]) for ident, s in self.partial.items()}


def pow_valid(raw: bytes) -> bool:
    """The self-authenticating check: does this block meet its own target?"""
    if len(raw) < 80:
        return False
    header = raw[:80]
    bits = int.from_bytes(header[72:76], "little")
    try:
        return int(block_hash(header), 16) <= target_from_bits(bits)
    except Exception:
        return False


def airtime_estimate_s(n_fragments: int, sf: int = 9, bw_khz: int = 125,
                       payload_bytes: int = DEFAULT_MTU) -> float:
    """Rough LoRa airtime for a whole block, for planning duty cycle.

    Standard Semtech formulation, coding rate 4/5, explicit header, preamble 8.
    Approximate by design — it is used to choose a repeat interval, not to
    certify compliance with any regulator's duty-cycle limit.
    """
    t_sym = (2 ** sf) / (bw_khz * 1000.0)
    preamble = (8 + 4.25) * t_sym
    de = 1 if (sf >= 11 and bw_khz == 125) else 0
    num = 8 * payload_bytes - 4 * sf + 28 + 16
    den = 4 * (sf - 2 * de)
    n_payload = 8 + max(0, -(-num // den)) * 5      # ceil(num/den) * (CR+4=5)
    return n_fragments * (preamble + n_payload * t_sym)
