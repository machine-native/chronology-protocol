#!/usr/bin/env python3
"""G5 acquisition: authenticated Roughtime witnesses beside NTP -> epoch-3 checkpoint.

Fresh B0 and challenge; two chained rounds against each live Roughtime server
(responses fully verified: Merkle inclusion of the challenge-derived nonce,
Ed25519 response + delegation signatures against pinned long-term keys) beside
two rounds of the five NTP witnesses; epoch-3 checkpoint chained to the epoch-2
(astronomical) checkpoint.
"""
from __future__ import annotations
import base64, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_sandwich import HOSTS, keypairs, fetch_tip_block
from ctp import cbor
from ctp.genesis import build_protocol_genesis
from ctp.model import build_checkpoint, sign_checkpoint, sign_observation
from ctp.bitcoin_jan09 import anchor_payload, dsha
from ctp.pq import ensure_available
from ctp.sandwich import (challenge, exchange_nonce, ntp_exchange, derive_measurement,
                          evidence_blob, ntp_unsigned, rt_unsigned, SandwichBundle)
from ctp.roughtime import (rt_nonce, roughtime_exchange, verify_response,
                           derive_rt_measurement, rt_evidence_blob)

# Long-term keys from the pinned ecosystem snapshot (docs/REALITY-SANDWICH.md §3;
# provenance: cloudflare/roughtime ecosystem.json, fetched 2026-08-21)
RT_SERVERS = [
    ("roughtime.cloudflare.com", 2003, "0GD7c3yP8xEc4Zl2zeuN2SlLvDVVocjsPSL8/Rl/7zg="),
    ("time.txryan.com", 2002, "iBVjxg/1j7y1+kQUTBYdTabxCppesU/07D4PMDJk2WA="),
]


def main():
    ensure_available()
    work = ROOT / "live" / "g5-work"
    work.mkdir(parents=True, exist_ok=True)

    b0_raw, b0_height = fetch_tip_block()
    b0_hash = dsha(b0_raw[:80])[::-1].hex()
    session_id = os.urandom(32)
    q = challenge(b0_hash, session_id)
    origin_s = (int(time.time()) // 86400) * 86400
    print(f"B0: {b0_hash} height {b0_height}")

    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()

    history, latest, blobs = [], [], []

    # Roughtime witnesses (verified before acceptance)
    for host, port, key64 in RT_SERVERS:
        lt = base64.b64decode(key64)
        records = []
        try:
            for seq in (0, 1):
                n = rt_nonce(q, host, seq)
                ex = roughtime_exchange(host, port, n)
                verified = verify_response(ex["response"], n, lt)
                meas = derive_rt_measurement(ex, verified)
                blob = rt_evidence_blob(seq, ex, lt, q, b0_hash, session_id)
                records.append((ex, meas, blob))
                print(f"  RT {host} seq {seq}: signed midp={verified['midp_s']} "
                      f"±{meas['uncertainty_ps']/1e12:.2f}s")
        except Exception as e:
            print(f"  RT {host}: dropped ({e})")
            continue
        keys = keypairs(work / "keys", "rt-" + host.replace(".", "-"))
        prev = None
        for seq, (ex, meas, blob) in enumerate(records):
            u = rt_unsigned(seq, ex, meas, blob, gid, prev, origin_s)
            s = sign_observation(u, keys)
            prev = u.lineage_id()
            history.append(s)
            blobs.append(blob)
            if seq == 1:
                latest.append(s)

    # NTP witnesses
    exchanges = {}
    for seq in (0, 1):
        for host in HOSTS:
            if seq == 1 and host not in exchanges:
                continue
            nonce = exchange_nonce(q, host, seq)
            try:
                ex = ntp_exchange(host, nonce)
            except Exception:
                exchanges.pop(host, None)
                continue
            if ex["response"][24:32] != nonce:
                exchanges.pop(host, None)
                continue
            exchanges.setdefault(host, {})[seq] = (ex, derive_measurement(ex),
                                                   evidence_blob(seq, ex, q, b0_hash, session_id))
    complete = {h: r for h, r in exchanges.items() if 0 in r and 1 in r}
    for host in sorted(complete):
        keys = keypairs(work / "keys", host.replace(".", "-"))
        prev = None
        for seq in (0, 1):
            ex, meas, blob = complete[host][seq]
            u = ntp_unsigned(seq, ex, meas, blob, gid, prev, origin_s)
            s = sign_observation(u, keys)
            prev = u.lineage_id()
            history.append(s)
            blobs.append(blob)
            if seq == 1:
                latest.append(s)
    print(f"witnesses: {len(latest)} ({len(latest) - len(complete)} Roughtime, {len(complete)} NTP)")
    if len(latest) < 4:
        raise SystemExit("consensus needs N >= 3f+1 = 4")

    prev_bundle = SandwichBundle.from_bytes(
        (ROOT / "vectors" / "valid" / "astro-sandwich-bundle.cbor").read_bytes())
    previous = prev_bundle.checkpoint.record_commitment()
    cp = build_checkpoint(3, latest, f=1, previous=previous)
    scp = sign_checkpoint(cp, keypairs(work / "keys", "checkpoint"))
    commitment = scp.record_commitment()
    payload = anchor_payload(cp.epoch, commitment.sha256, commitment.shake384)

    (work / "challenge.json").write_text(json.dumps(
        {"b0_hash": b0_hash, "b0_height": b0_height, "b0_raw_hex": b0_raw.hex(),
         "session_id": session_id.hex(), "challenge": q.hex(),
         "issued_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    for i, blob in enumerate(blobs):
        (work / f"blob{i:02d}.cbor").write_bytes(blob)
    (work / "history.cbor").write_bytes(cbor.dumps([s.as_obj() for s in history]))
    (work / "checkpoint.cbor").write_bytes(scp.canonical())
    (work / "payload.hex").write_text(payload.hex() + "\n")

    print(json.dumps({
        "consensus": {"verdict": cp.verdict, "q": cp.q, "witnesses": cp.witness_count,
                      "interval_ps": None if cp.interval is None else [cp.interval.lower, cp.interval.upper]},
        "checkpoint_epoch": cp.epoch, "payload_hex": payload.hex()}, indent=2))


if __name__ == "__main__":
    main()
