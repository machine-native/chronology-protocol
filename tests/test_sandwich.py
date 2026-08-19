import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp import cbor
from ctp.genesis import build_protocol_genesis
from ctp.model import build_checkpoint, sign_checkpoint, sign_observation
from ctp.bitcoin_jan09 import anchor_payload, make_block, block_hash
from ctp.pq import ensure_available, generate_keypair, PQUnavailable, ML_DSA_87, SLH_DSA_SHAKE_256S
from ctp.sandwich import (challenge, exchange_nonce, frame_for_origin, parse_frame_origin,
                          derive_measurement, evidence_blob, ntp_unsigned, era_expectation,
                          SandwichBundle, verify_sandwich, NTP_UNIX_DELTA, PS,
                          LOCAL_TIMESTAMP_MARGIN_PS)

B0_HASH = "00" * 32
EASY_BITS = 0x2100FFFF   # test-only: nearly every hash satisfies the target


def test_challenge_and_nonce_derivation_deterministic():
    session = bytes(range(32))
    q1 = challenge(B0_HASH, session)
    q2 = challenge(B0_HASH, session)
    assert q1 == q2 and len(q1) == 32
    assert challenge(B0_HASH, bytes(32)) != q1
    n_a0 = exchange_nonce(q1, "a.example", 0)
    assert len(n_a0) == 8
    assert n_a0 != exchange_nonce(q1, "a.example", 1)
    assert n_a0 != exchange_nonce(q1, "b.example", 0)
    with pytest.raises(ValueError):
        challenge(B0_HASH, b"short")


def test_frame_origin_roundtrip():
    assert parse_frame_origin(frame_for_origin(1787097600)) == 1787097600
    with pytest.raises(ValueError):
        parse_frame_origin("SIMULATED-TAU/v1")


def _ntp_ts(unix_ps: int) -> bytes:
    secs = unix_ps // PS + NTP_UNIX_DELTA
    frac = ((unix_ps % PS) << 32) // PS
    return struct.pack(">II", secs, frac)


def synthetic_exchange(host: str, nonce8: bytes, base_unix_s: int, offset_ns: int = 0):
    req = bytearray(48)
    req[0] = 0x23
    req[40:48] = nonce8
    t2_ps = base_unix_s * PS + offset_ns * 1000
    t3_ps = t2_ps + 1_000_000_000        # 1 ms server processing
    resp = bytearray(48)
    resp[0] = 0x24                        # LI=0 VN=4 mode=4 (server)
    resp[1] = 2                           # stratum
    resp[4:8] = struct.pack(">HH", 0, 1 << 8)   # root delay ~3.9 ms
    resp[8:12] = struct.pack(">HH", 0, 1 << 8)  # root dispersion ~3.9 ms
    resp[24:32] = nonce8                  # originate echo
    resp[32:40] = _ntp_ts(t2_ps)
    resp[40:48] = _ntp_ts(t3_ps)
    return {"host": host, "ip": "192.0.2.1", "request": bytes(req), "response": bytes(resp),
            "t1_utc_ns": base_unix_s * 10**9, "t1_mono_ns": 5_000_000_000,
            "t4_mono_ns": 5_000_000_000 + 11_000_000}    # 11 ms rtt


def test_measurement_derivation_math():
    ex = synthetic_exchange("a.example", b"\x11" * 8, 1_787_000_000)
    m = derive_measurement(ex)
    # rtt 11ms, server 1ms -> path 10ms -> claimed = t3 + 5ms
    # (tolerance: NTP 32-bit fraction encode/decode rounds by < 1 ns)
    t3_ps = 1_787_000_000 * PS + 1_000_000_000
    assert abs(m["claimed_ps"] - (t3_ps + 5_000_000_000)) < 1_000
    assert m["uncertainty_ps"] > 5_000_000_000 + LOCAL_TIMESTAMP_MARGIN_PS
    assert m["mode"] == 4 and m["stratum"] == 2


def test_era_expectation_integer_and_sane():
    # 2026-08-19T12:00:00Z — ERA must be a valid nano-turn phase with small stated bound
    e = era_expectation(1_787_097_600, 43_200 * PS)
    assert 0 <= e[4] < 1_000_000_000
    assert 0 < e[5] < 50_000            # DUT1 bound ~10.4k nano-turns
    assert e[7] == "EXPECTATION_NOT_EVIDENCE"
    assert e == era_expectation(1_787_097_600, 43_200 * PS)


def _pq_keys(tmp: Path, name: str):
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for alg, slug in [(ML_DSA_87, "m"), (SLH_DSA_SHAKE_256S, "s")]:
        priv, pub = d / f"{slug}.pem", d / f"{slug}.pub.pem"
        generate_keypair(alg, priv, pub)
        out.append((alg, priv, pub))
    return out


def _mine_easy(payload: bytes, prev: str, ntime: int):
    for nonce in range(200):
        b = make_block(payload, prev, ntime, EASY_BITS, nonce=nonce)
        if b["pow_valid"]:
            return b
    raise AssertionError("no easy nonce found")


def _synthetic_sandwich(tmp: Path):
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()
    b0 = _mine_easy(anchor_payload(0, b"\x00" * 32, b"\x00" * 48), "11" * 32, 1_787_000_000)
    session = bytes(range(32))
    q = challenge(b0["hash"], session)
    origin_s = 1_787_000_000 - (1_787_000_000 % 86400)

    history, latest, blobs = [], [], []
    for host in ("a.example", "b.example", "c.example", "d.example"):
        keys = _pq_keys(tmp, host)
        prev_lineage = None
        for seq in (0, 1):
            ex = synthetic_exchange(host, exchange_nonce(q, host, seq),
                                    1_787_000_100 + seq, offset_ns=hash(host) % 1000)
            meas = derive_measurement(ex)
            blob = evidence_blob(seq, ex, q, b0["hash"], session)
            u = ntp_unsigned(seq, ex, meas, blob, gid, prev_lineage, origin_s)
            s = sign_observation(u, keys)
            prev_lineage = u.lineage_id()
            history.append(s)
            blobs.append(blob)
            if seq == 1:
                latest.append(s)
    cp = build_checkpoint(1, latest, f=1)
    scp = sign_checkpoint(cp, _pq_keys(tmp, "coord"))
    commitment = scp.record_commitment()
    payload = anchor_payload(1, commitment.sha256, commitment.shake384)
    c = _mine_easy(payload, b0["hash"], 1_787_000_200)
    b1 = _mine_easy(anchor_payload(2, b"\x01" * 32, b"\x01" * 48), c["hash"], 1_787_000_300)
    mid_rel = (cp.interval.lower + cp.interval.upper) // 2
    return SandwichBundle(
        b0_raw=b0["raw"], b0_height=1, session_id=session, evidence=blobs,
        history=history, checkpoint=scp, block_c_raw=c["raw"], path_headers=[],
        b1_headers=[b1["header"]], expectation=era_expectation(origin_s, mid_rel),
        genesis=genesis)


def test_synthetic_sandwich_roundtrip_and_tamper(tmp_path):
    try:
        ensure_available()
    except PQUnavailable:
        pytest.skip("OpenSSL with ML-DSA/SLH-DSA unavailable")
    bundle = _synthetic_sandwich(tmp_path)
    raw = bundle.canonical()
    checks, verdict, facts = verify_sandwich(SandwichBundle.from_bytes(raw))
    assert verdict == "SANDWICH_PASS", checks
    assert facts["burial_depth"] == 1

    # tamper: flip one byte inside the first evidence blob
    tampered = SandwichBundle.from_bytes(raw)
    blob = bytearray(tampered.evidence[0])
    blob[-1] ^= 0x01
    tampered.evidence[0] = bytes(blob)
    checks2, verdict2, _ = verify_sandwich(tampered)
    assert verdict2 == "FAIL"
    assert not (checks2["S_EVIDENCE_MEASUREMENT"] and checks2["S_CHALLENGE_BINDING"]
                and checks2["S_NONCE_ECHO"]) or not checks2["S_EVIDENCE_MEASUREMENT"]

    # tamper: different session id breaks the challenge chain
    wrong = SandwichBundle.from_bytes(raw)
    wrong.session_id = bytes(32)
    checks3, verdict3, _ = verify_sandwich(wrong)
    assert verdict3 == "FAIL" and not checks3["S_NONCE_ECHO"]
