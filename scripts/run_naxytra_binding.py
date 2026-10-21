#!/usr/bin/env python3
"""Epoch 10: bind two NAXYTRA-ATTESTATION/1 records into a reality sandwich.

The second half of an external-record binding whose first half ran on 2026-10-21
and is held in live/naxytra-bind-work/challenge.json. That file fixes B0 (1364),
the session id and the challenge q; the derived binding tag went to the external
system, which carried it INSIDE the signed bytes of each attestation. This script
does not re-mint anything. A fresh B0 here would orphan the attestations already
bound to the old tag, which is the one failure a round-trip binding adds over a
single-run one.

What it does, in the epoch-5 shape (scripts/run_satroot_binding.py):

    NTP round on q          five operators, two exchanges each, nonce echoed
    external record blobs   one per attestation, EXTERNAL-RECORD/v1, digest only
    checkpoint              epoch 10, chained to epoch 9 (live/cw-bind-work)
    payload                 96 bytes, for the coinbase of block C

What crosses the boundary: the two attestation digests, recorded in
live/naxytra-bind-work/records.json after independent recomputation. The
attestations' content never enters this directory or the bundle.

Then: mine C carrying the payload (live/race.sh), bury, assemble, OTS.
"""
from __future__ import annotations
import hashlib, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_sandwich import HOSTS, keypairs
from ctp import cbor
from ctp.binding import binding_tag, external_record_blob
from ctp.genesis import build_protocol_genesis
from ctp.model import (SignedCheckpoint, build_checkpoint, sign_checkpoint,
                       sign_observation)
from ctp.bitcoin_jan09 import anchor_payload
from ctp.pq import ensure_available
from ctp.sandwich import (challenge, exchange_nonce, ntp_exchange,
                          derive_measurement, evidence_blob, ntp_unsigned)

EPOCH = 10
PREV_WORK = "live/cw-bind-work"             # epoch 9
SYSTEM_ID = "NAXYTRA-ATTESTATION/1"
WORK = ROOT / "live" / "naxytra-bind-work"


def main() -> int:
    ensure_available()
    ch = json.loads((WORK / "challenge.json").read_text(encoding="utf-8"))
    recs = json.loads((WORK / "records.json").read_text(encoding="utf-8"))
    if ch["system_id"] != SYSTEM_ID or recs["system_id"] != SYSTEM_ID:
        raise SystemExit("system_id mismatch between challenge.json and records.json")

    b0_hash, b0_height = ch["b0_hash"], ch["b0_height"]
    session_id = bytes.fromhex(ch["session_id"])
    q = challenge(b0_hash, session_id)
    if q.hex() != ch["challenge"]:
        raise SystemExit("challenge.json's q does not re-derive from its own B0 and "
                         "session_id; the session file is corrupt")
    tag = binding_tag(q, SYSTEM_ID)
    if tag.hex() != ch["binding_tag"]:
        raise SystemExit("binding tag does not re-derive; refusing to bind")
    if (WORK / "payload.hex").exists():
        raise SystemExit("payload.hex already exists; this half has already run")

    print(f"\nepoch {EPOCH} · {SYSTEM_ID}")
    print(f"  B0 height {b0_height}  {b0_hash}")
    print(f"  session   {session_id.hex()}")
    print(f"  tag       {tag.hex()}  (re-derived, matches)")
    print(f"  records   {len(recs['records'])}")
    for r in recs["records"]:
        print(f"    seq {r['seq']}  {r['attestation_id']}  {r['record_sha256']}")

    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()
    origin_s = (int(time.time()) // 86400) * 86400

    print("\n  NTP round on the same challenge:")
    exchanges = {}
    for seq in (0, 1):
        for host in HOSTS:
            if seq == 1 and host not in exchanges:
                continue
            nonce = exchange_nonce(q, host, seq)
            try:
                ex = ntp_exchange(host, nonce)
            except Exception as e:
                print(f"    {host} seq {seq}: FAILED ({e})")
                exchanges.pop(host, None)
                continue
            if ex["response"][24:32] != nonce:
                print(f"    {host} seq {seq}: nonce not echoed, dropped")
                exchanges.pop(host, None)
                continue
            meas = derive_measurement(ex)
            exchanges.setdefault(host, {})[seq] = (
                ex, meas, evidence_blob(seq, ex, q, b0_hash, session_id))
            print(f"    {host} seq {seq}: ok rtt {meas['rtt_ps']/1e9:.0f}ms")
    complete = {h: r for h, r in exchanges.items() if 0 in r and 1 in r}
    if len(complete) < 3:
        raise SystemExit(f"too few NTP witnesses ({len(complete)}); need 3")

    history, latest, blobs = [], [], []
    wkeys = {h: keypairs(WORK / "keys", h.replace(".", "-")) for h in complete}
    for host in sorted(complete):
        ex0, m0, b0b = complete[host][0]
        ex1, m1, b1b = complete[host][1]
        u0 = ntp_unsigned(0, ex0, m0, b0b, gid, None, origin_s)
        s0 = sign_observation(u0, wkeys[host])
        u1 = ntp_unsigned(1, ex1, m1, b1b, gid, u0.lineage_id(), origin_s)
        s1 = sign_observation(u1, wkeys[host])
        history += [s0, s1]
        latest.append(s1)
        blobs += [b0b, b1b]

    # One EXTERNAL-RECORD/v1 blob per attestation. Digest only.
    for r in sorted(recs["records"], key=lambda x: x["seq"]):
        rec_sha = bytes.fromhex(r["record_sha256"])
        blob = external_record_blob(r["seq"], SYSTEM_ID, rec_sha, q, b0_hash, session_id)
        blobs.append(blob)
        (WORK / f"naxytra-binding-blob-{r['seq']}.cbor").write_bytes(blob)

    prev = SignedCheckpoint.from_obj(
        cbor.loads((ROOT / PREV_WORK / "checkpoint.cbor").read_bytes()))
    if prev.unsigned.epoch != EPOCH - 1:
        raise SystemExit(f"{PREV_WORK} is epoch {prev.unsigned.epoch}, not {EPOCH - 1}")
    cp = build_checkpoint(EPOCH, latest, f=1, previous=prev.record_commitment())
    scp = sign_checkpoint(cp, keypairs(WORK / "keys", "checkpoint"))
    commitment = scp.record_commitment()
    payload = anchor_payload(cp.epoch, commitment.sha256, commitment.shake384)

    for i, blob in enumerate(blobs):
        (WORK / f"blob{i:02d}.cbor").write_bytes(blob)
    (WORK / "history.cbor").write_bytes(cbor.dumps([s.as_obj() for s in history]))
    (WORK / "checkpoint.cbor").write_bytes(scp.canonical())
    (WORK / "payload.hex").write_text(payload.hex() + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({
        "epoch": cp.epoch,
        "system_id": SYSTEM_ID,
        "binding_tag": tag.hex(),
        "records": [{"seq": r["seq"], "attestation_id": r["attestation_id"],
                     "record_sha256": r["record_sha256"]} for r in recs["records"]],
        "witnesses": sorted(complete) + [f"{SYSTEM_ID} x{len(recs['records'])}"],
        "previous_epoch": prev.unsigned.epoch,
        "checkpoint_sha256": commitment.sha256.hex(),
        "payload_hex": payload.hex(),
    }, indent=2))
    print("\n  Next: PAYLOAD_HEX=$(cat live/naxytra-bind-work/payload.hex) CORES=16 bash live/race.sh\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
