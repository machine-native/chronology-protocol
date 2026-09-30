"""Evidence types this repository does not implement, verified by extensions.

A witness profile can live in its own repository and still sit in a sandwich:
`verify_sandwich(bundle, extensions={type: verifier})`. These tests use a stand-in
type, TEST-EXT/v1, so they depend on nothing outside this repository.

The property that matters most is the last one here: evidence nobody can check is
NOT_CHECKED, and NOT_CHECKED can never turn a FAIL into anything else.
"""
from pathlib import Path

import pytest

from ctp import cbor
from ctp.bitcoin_jan09 import anchor_payload
from ctp.genesis import build_protocol_genesis
from ctp.hashsuite import digest_pair, DOM_EVIDENCE, DOM_STATE, DOM_WITNESS
from ctp.interval import Interval
from ctp.model import (SourceObservation, UnsignedObservation, build_checkpoint,
                       sign_checkpoint, sign_observation)
from ctp.pq import PQUnavailable, ensure_available
from ctp.sandwich import (NOT_CHECKED, SandwichBundle, challenge, derive_measurement,
                          era_expectation, evidence_blob, exchange_nonce, frame_for_origin,
                          ntp_unsigned, verify_sandwich, PS)

from test_sandwich import _mine_easy, _pq_keys, synthetic_exchange

ROOT = Path(__file__).resolve().parents[1]
EXT = "TEST-EXT/v1"


def _ext_blob(q, b0_hash, session, claimed_rel_ps, unc_ps, bound=True):
    return cbor.dumps({1: EXT, 2: claimed_rel_ps, 3: unc_ps,
                       10: q if bound else bytes(32), 11: bytes.fromhex(b0_hash), 12: session})


def _build(tmp: Path, *, ext_bound=True, break_ntp=False):
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()
    b0 = _mine_easy(anchor_payload(0, b"\x00" * 32, b"\x00" * 48), "11" * 32, 1_787_000_000)
    session = bytes(range(32))
    q = challenge(b0["hash"], session)
    origin_s = 1_787_000_000 - (1_787_000_000 % 86400)
    history, latest, blobs = [], [], []
    for host in ("a.example", "b.example", "c.example", "d.example"):
        ex = synthetic_exchange(host, exchange_nonce(q, host, 0), 1_787_000_100)
        blob = evidence_blob(0, ex, q, b0["hash"], session)
        s = sign_observation(ntp_unsigned(0, ex, derive_measurement(ex), blob, gid, None,
                                          origin_s), _pq_keys(tmp, host))
        history.append(s)
        latest.append(s)
        blobs.append(blob)
    rel = 1_787_000_100 * PS - origin_s * PS
    eblob = _ext_blob(q, b0["hash"], session, rel, 50 * 10**9, bound=ext_bound)
    ev = digest_pair(DOM_EVIDENCE, eblob)
    state = digest_pair(DOM_STATE, b"test-ext")
    u = UnsignedObservation(
        witness_id=digest_pair(DOM_WITNESS, b"TEST-EXT:one").sha256, genesis_id=gid,
        sequence=0, previous=None, monotonic_ps=1,
        interval=Interval(rel - 50 * 10**9, rel + 50 * 10**9),
        reference_frame=frame_for_origin(origin_s),
        sources=[SourceObservation(EXT, rel, 50 * 10**9, "TEST", ev)],
        hardware_state=state, firmware_state=state)
    s = sign_observation(u, _pq_keys(tmp, "ext"))
    history.append(s)
    latest.append(s)
    blobs.append(eblob)
    if break_ntp:
        bad = bytearray(blobs[0])
        bad[-1] ^= 1
        blobs[0] = bytes(bad)
    cp = build_checkpoint(1, latest, f=1)
    scp = sign_checkpoint(cp, _pq_keys(tmp, "coord"))
    com = scp.record_commitment()
    c = _mine_easy(anchor_payload(1, com.sha256, com.shake384), b0["hash"], 1_787_000_200)
    b1 = _mine_easy(anchor_payload(2, b"\x01" * 32, b"\x01" * 48), c["hash"], 1_787_000_300)
    mid = (cp.interval.lower + cp.interval.upper) // 2
    return SandwichBundle(b0_raw=b0["raw"], b0_height=1, session_id=session, evidence=blobs,
                          history=history, checkpoint=scp, block_c_raw=c["raw"],
                          path_headers=[], b1_headers=[b1["header"]],
                          expectation=era_expectation(origin_s, mid), genesis=genesis)


def _checker(result, facts=None):
    seen = []

    def verify(u, blob, same):
        seen.append((u.sequence, cbor.loads(blob)[1], len(same)))
        return result, dict(facts or {})
    verify.seen = seen
    return verify


@pytest.fixture(scope="module")
def pq():
    try:
        ensure_available()
    except PQUnavailable:
        pytest.skip("OpenSSL with ML-DSA/SLH-DSA unavailable")


@pytest.fixture(scope="module")
def bundle(pq, tmp_path_factory):
    return _build(tmp_path_factory.mktemp("ext"))


def test_without_the_extension_the_evidence_is_not_checked_and_nothing_passes(bundle):
    checks, verdict, facts = verify_sandwich(bundle)
    assert verdict == "INDETERMINATE_UNCHECKED_EVIDENCE"
    assert checks["S_UNCHECKED_EVIDENCE"] == NOT_CHECKED
    assert facts["unchecked_evidence_types"] == [EXT]
    # everything this repository can check about it still ran and held
    assert checks["S_CHALLENGE_BINDING"] and checks["S_EVIDENCE_MEASUREMENT"]


def test_an_extension_that_verifies_gives_a_pass_and_its_facts(bundle):
    ext = _checker(True, {"note": "checked"})
    checks, verdict, facts = verify_sandwich(bundle, {EXT: ext})
    assert verdict == "SANDWICH_PASS", checks
    assert checks["S_EXTENSION_EVIDENCE"] is True
    assert ext.seen == [(0, EXT, 1)]
    (f,) = facts["extensions"]
    assert f["type"] == EXT and f["result"] is True and f["note"] == "checked"


def test_an_extension_that_refuses_gives_a_fail(bundle):
    checks, verdict, _ = verify_sandwich(bundle, {EXT: _checker(False)})
    assert verdict == "FAIL" and checks["S_EXTENSION_EVIDENCE"] is False


def test_an_extension_that_cannot_check_is_indeterminate(bundle):
    checks, verdict, _ = verify_sandwich(bundle, {EXT: _checker(NOT_CHECKED)})
    assert verdict == "INDETERMINATE_UNCHECKED_EVIDENCE"


def test_an_extension_that_crashes_is_a_fail_not_a_pass(bundle):
    def boom(u, blob, same):
        raise RuntimeError("extension bug")
    checks, verdict, facts = verify_sandwich(bundle, {EXT: boom})
    assert verdict == "FAIL" and "extension bug" in facts["extensions"][0]["error"]


def test_evidence_not_bound_to_the_session_still_fails(pq, tmp_path):
    b = _build(tmp_path, ext_bound=False)
    checks, verdict, _ = verify_sandwich(b, {EXT: _checker(True)})
    assert verdict == "FAIL" and not checks["S_CHALLENGE_BINDING"]


def test_unchecked_evidence_cannot_mask_a_failure(pq, tmp_path):
    # A bundle that fails on its own (a tampered NTP blob) must still FAIL when it
    # also carries evidence nobody here can check -- adding such a blob must never
    # buy a softer verdict.
    b = _build(tmp_path, break_ntp=True)
    checks, verdict, _ = verify_sandwich(b)
    assert checks["S_UNCHECKED_EVIDENCE"] == NOT_CHECKED
    assert verdict == "FAIL"
