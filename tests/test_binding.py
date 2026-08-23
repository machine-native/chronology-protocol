"""Tests for binding an external record into a reality sandwich.

The property under test is an asymmetry that is easy to get wrong and whose
failure is silent: committing the sandwich to a record's hash proves only that
the record existed BEFORE the closing block. It says nothing about when the
record was made. A record produced years earlier can be committed today and the
bytes are indistinguishable.

So the tests below deliberately construct each half-binding on its own and
require the verifier to name it as a half. A verifier that returned "pass" for
an upper bound alone would let a backdated record wear a sandwich.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp import cbor
from ctp.binding import (binding_tag, external_record_blob, verify_binding,
                         DOM_EXTBIND, PROFILE)
from ctp.bitcoin_jan09 import block_hash
from ctp.sandwich import SandwichBundle, challenge

VECTORS = ROOT / "vectors" / "valid"


def _bundle():
    p = VECTORS / "reality-sandwich-bundle.cbor"
    if not p.is_file():
        pytest.skip("no sandwich bundle present")
    return SandwichBundle.from_bytes(p.read_bytes())


def _q(b):
    return challenge(block_hash(b.b0_raw[:80]), b.session_id)


def test_tag_is_domain_separated_and_system_scoped():
    """One session must not yield the same tag in two systems, or a record in
    one could be correlated with -- or replayed into -- the other."""
    q = b"\x11" * 32
    a = binding_tag(q, "SATROOT1")
    b = binding_tag(q, "SENSOR-BATCH/v1")
    assert a != b
    assert len(a) == 32
    # and the tag must not be the challenge itself, or the record leaks q
    assert a != q
    assert hashlib.sha256(DOM_EXTBIND + b"\x00" + q + b"SATROOT1").digest() == a


def test_tag_depends_on_the_challenge():
    """If the tag did not depend on q it would carry no time information."""
    assert binding_tag(b"\x11" * 32, "S") != binding_tag(b"\x22" * 32, "S")


def test_full_binding_is_recognised():
    b = _bundle()
    q = _q(b)
    record = json.dumps({
        "namespace": "demo",
        "chrn_binding": binding_tag(q, "SATROOT1").hex(),
    }, separators=(",", ":")).encode()
    h = hashlib.sha256(record).digest()
    b.evidence = list(b.evidence) + [
        external_record_blob(0, "SATROOT1", h, q, block_hash(b.b0_raw[:80]), b.session_id)
    ]
    checks, verdict = verify_binding(b, "SATROOT1", record)
    assert verdict == "BOUND", checks
    assert checks["RECORD_CARRIES_BINDING_TAG"] is True
    assert checks["SANDWICH_COMMITS_TO_RECORD"] is True


def test_sandwich_commitment_alone_is_only_an_upper_bound():
    """THE POINT OF THE MODULE. A record with no tag could predate B0 by years."""
    b = _bundle()
    q = _q(b)
    record = b'{"namespace":"demo","made":"long ago"}'
    h = hashlib.sha256(record).digest()
    b.evidence = list(b.evidence) + [
        external_record_blob(0, "SATROOT1", h, q, block_hash(b.b0_raw[:80]), b.session_id)
    ]
    checks, verdict = verify_binding(b, "SATROOT1", record)
    assert verdict == "UPPER_ONLY", checks
    assert verdict != "BOUND", "a backdated record must not read as sandwiched"


def test_tag_alone_is_only_a_lower_bound():
    """Nothing closes the interval from above if the sandwich never commits."""
    b = _bundle()
    record = json.dumps({"t": binding_tag(_q(b), "SATROOT1").hex()}).encode()
    checks, verdict = verify_binding(b, "SATROOT1", record)
    assert verdict == "LOWER_ONLY", checks


def test_unrelated_record_is_unbound():
    b = _bundle()
    checks, verdict = verify_binding(b, "SATROOT1", b"nothing to do with anything")
    assert verdict == "UNBOUND", checks


def test_a_blob_from_another_session_does_not_bind():
    """Evidence must be nailed to ITS session, or a blob could be lifted across."""
    b = _bundle()
    q = _q(b)
    record = json.dumps({"t": binding_tag(q, "SATROOT1").hex()}).encode()
    h = hashlib.sha256(record).digest()
    foreign = external_record_blob(0, "SATROOT1", h, q,
                                   block_hash(b.b0_raw[:80]), b"\x00" * 32)
    b.evidence = list(b.evidence) + [foreign]
    checks, verdict = verify_binding(b, "SATROOT1", record)
    assert verdict == "LOWER_ONLY", "a foreign session_id must not satisfy the upper bound"


def test_the_tag_must_match_the_system_it_claims():
    """A tag minted for one system must not bind a record in another."""
    b = _bundle()
    q = _q(b)
    record = json.dumps({"t": binding_tag(q, "SOME-OTHER-SYSTEM").hex()}).encode()
    checks, verdict = verify_binding(b, "SATROOT1", record)
    assert verdict == "UNBOUND", checks


def test_both_hex_and_raw_encodings_are_accepted_and_named():
    """JSON systems carry hex, binary systems carry bytes. Both are legitimate;
    which one was found is reported because an unexpected encoding usually means
    the producer improvised."""
    b = _bundle()
    tag = binding_tag(_q(b), "SATROOT1")
    for record, expect in ((b"prefix" + tag + b"suffix", "raw"),
                           (tag.hex().encode(), "hex-lower"),
                           (tag.hex().upper().encode(), "hex-upper")):
        checks, verdict = verify_binding(b, "SATROOT1", record)
        assert checks["TAG_ENCODING"] == expect, (expect, checks)
        assert verdict == "LOWER_ONLY"


def test_blob_rejects_a_wrong_length_hash():
    with pytest.raises(ValueError):
        external_record_blob(0, "S", b"\x00" * 31, b"\x11" * 32, "00" * 32, b"\x00" * 32)
