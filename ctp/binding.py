"""Binding an external record into a reality sandwich (CHRN external-binding v1).

A sandwich proves an acquisition happened between two proof-of-work blocks. This
module lets a record produced by some OTHER system -- a SATROOT event, a sensor
batch, any content-addressed artifact -- obtain the same bound.

THE ASYMMETRY THAT MAKES IT WORK

The obvious construction is to put the record's hash into the sandwich and stop
there. That is only half a binding, and the half it gives is the weaker one:

    sandwich commits to H   =>   H existed BEFORE B1        (upper bound)

It says nothing about when H was made. A record produced last year can be
committed today, and the bytes look identical either way. Publication order is
not creation order.

The lower bound has to travel in the opposite direction. The challenge

    q = SHA-256(DOM || hash(B0) || session_id)

cannot be computed before B0 is mined, so a record that CONTAINS q could not have
existed before B0 did:

    record commits to q     =>   record created AFTER B0    (lower bound)

Both directions, and only both, give the sandwich property:

    B0  <  record  <  B1

This is the same structure as the rolling-code photographs, where the code has to
be visible IN the frame rather than quoted afterwards. A reference added later
proves nothing about the moment; a value that could not have been guessed does.

WHAT THE EXTERNAL SYSTEM MUST DO

Carry `binding_tag(q, system_id)` inside the record it signs, in whatever field it
has. The tag rather than q itself, so that two systems bound to the same session
do not share a correlatable value, and so a system with a short field can carry a
prefix without leaking the challenge.

WHAT THIS MODULE DOES NOT DO

It does not verify the external record. Whether a SATROOT event is validly signed
is SATROOT's question, answered by SATROOT's verifier. This establishes only WHEN
the bytes existed -- which is exactly the gap that signatures, attestation and
hash chains leave open, and exactly the thing proof-of-work can close.
"""
from __future__ import annotations
import hashlib
from typing import Optional

from . import cbor
from .bitcoin_jan09 import block_hash
from .sandwich import challenge

DOM_EXTBIND = b"CHRONOLOGY/EXTERNAL-BINDING/v1"
PROFILE = "EXTERNAL-RECORD/v1"


def binding_tag(q: bytes, system_id: str) -> bytes:
    """The 32 bytes the external record must carry.

    Domain-separated and system-scoped: the same session yields a different tag
    per system, so a record in one system cannot be used to link a record in
    another, and neither reveals q.
    """
    if len(q) != 32:
        raise ValueError("challenge must be 32 bytes")
    if not system_id:
        raise ValueError("system_id must not be empty")
    return hashlib.sha256(DOM_EXTBIND + b"\x00" + q + system_id.encode("utf-8")).digest()


def external_record_blob(seq: int, system_id: str, record_sha256: bytes,
                         q: bytes, b0_hash_hex: str, session_id: bytes) -> bytes:
    """Evidence blob committing the sandwich to an external record's hash.

    Shaped like the other evidence blobs -- keys 10/11/12 carry the challenge,
    B0 and the session exactly as the NTP and camera blobs do -- so it is bound
    to one session and cannot be lifted into another.
    """
    if len(record_sha256) != 32:
        raise ValueError("record hash must be a 32-byte sha256")
    return cbor.dumps({
        1: PROFILE,
        2: system_id,
        3: record_sha256,
        4: binding_tag(q, system_id),
        5: seq,
        10: q,
        11: bytes.fromhex(b0_hash_hex),
        12: session_id,
    })


def _tag_present(record_bytes: bytes, tag: bytes) -> Optional[str]:
    """How the tag appears in the record, or None.

    Both encodings are accepted because both are legitimate: a CBOR or binary
    record carries raw bytes, while a JSON one -- SATROOT included -- carries
    hex text. Reporting WHICH was found is more useful than a boolean, since a
    tag in an unexpected encoding usually means the producer improvised.
    """
    if tag in record_bytes:
        return "raw"
    h = tag.hex().encode("ascii")
    if h in record_bytes:
        return "hex-lower"
    if h.upper() in record_bytes:
        return "hex-upper"
    return None


def verify_binding(bundle, system_id: str, record_bytes: bytes) -> tuple[dict, str]:
    """Check both directions of a binding. Returns (checks, verdict).

    Verdicts name what was established rather than collapsing to pass/fail,
    because the two half-bindings are genuinely different claims and a caller
    that treats an upper bound as a sandwich has been misled by the vocabulary:

      BOUND        both directions: B0 < record < B1
      UPPER_ONLY   the sandwich commits to the record, but the record does not
                   carry the tag -- the record may predate B0 by any amount
      LOWER_ONLY   the record carries the tag but the sandwich does not commit
                   to it -- nothing bounds it from above
      UNBOUND      neither
    """
    q = challenge(block_hash(bundle.b0_raw[:80]), bundle.session_id)
    tag = binding_tag(q, system_id)
    record_hash = hashlib.sha256(record_bytes).digest()

    encoding = _tag_present(record_bytes, tag)
    lower = encoding is not None

    upper = False
    for blob in bundle.evidence:
        try:
            obj = cbor.loads(blob)
        except Exception:
            continue
        if not isinstance(obj, dict) or obj.get(1) != PROFILE:
            continue
        if (obj.get(2) == system_id and obj.get(3) == record_hash
                and obj.get(4) == tag and obj.get(10) == q
                and obj.get(12) == bundle.session_id):
            upper = True
            break

    checks = {
        "RECORD_CARRIES_BINDING_TAG": lower,
        "TAG_ENCODING": encoding or "absent",
        "SANDWICH_COMMITS_TO_RECORD": upper,
        "RECORD_SHA256": record_hash.hex(),
        "BINDING_TAG": tag.hex(),
    }
    if lower and upper:
        verdict = "BOUND"
    elif upper:
        verdict = "UPPER_ONLY"
    elif lower:
        verdict = "LOWER_ONLY"
    else:
        verdict = "UNBOUND"
    return checks, verdict
