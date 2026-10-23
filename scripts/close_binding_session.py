#!/usr/bin/env python3
"""Close an external-binding session: NTP round, one blob per verified record, checkpoint, payload.

The second half of a round-trip binding, generalised from scripts/run_naxytra_binding.py
(epoch 10) so the weekly delegation-log cadence does not need a new script per epoch.
scripts/open_binding_session.py opened the session and sent the tag out; the external
system carried it inside its signed bytes; its records were re-fetched and verified into
records.json by hand. This binds exactly the entries records.json marks VERIFIED.

    python scripts/close_binding_session.py --work live/naxytra-delegation-work \
        --epoch 11 --prev-work live/naxytra-bind-work

Nothing is re-minted. q and the tag are re-derived from challenge.json and must match
it, or the script refuses: a fresh B0 here would orphan everything the external system
has already bound. Refuses if payload.hex exists -- the half has already run -- and
refuses to bind any record whose verdict is not VERIFIED, rather than skipping it quietly.

Then: PAYLOAD_HEX=$(cat <work>/payload.hex) CORES=16 bash live/race.sh
"""
from __future__ import annotations
import argparse, json, sys, time
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True)
    ap.add_argument("--epoch", type=int, required=True)
    ap.add_argument("--prev-work", required=True, help="work dir holding epoch N-1's checkpoint")
    a = ap.parse_args()

    ensure_available()
    work = ROOT / a.work
    ch = json.loads((work / "challenge.json").read_text(encoding="utf-8"))
    recs = json.loads((work / "records.json").read_text(encoding="utf-8"))
    system_id = ch["system_id"]
    if recs["system_id"] != system_id:
        raise SystemExit("system_id differs between challenge.json and records.json")

    b0_hash, b0_height = ch["b0_hash"], ch["b0_height"]
    session_id = bytes.fromhex(ch["session_id"])
    q = challenge(b0_hash, session_id)
    if q.hex() != ch["challenge"]:
        raise SystemExit("q does not re-derive from challenge.json's own B0 and session_id")
    tag = binding_tag(q, system_id)
    if tag.hex() != ch["binding_tag"]:
        raise SystemExit("binding tag does not re-derive; refusing to bind")
    if (work / "payload.hex").exists():
        raise SystemExit("payload.hex already exists in this work dir; this half has run")

    bound = [r for r in recs["records"] if r.get("verdict") == "VERIFIED"]
    refused = [r for r in recs["records"] if r.get("verdict") != "VERIFIED"]
    if not bound:
        raise SystemExit("no VERIFIED records to bind")
    if refused:
        raise SystemExit(f"{len(refused)} record(s) in records.json are not VERIFIED; "
                         "remove or re-verify them explicitly rather than binding around them")

    print(f"\nepoch {a.epoch} · {system_id}")
    print(f"  B0 height {b0_height}  {b0_hash}")
    print(f"  tag       {tag.hex()}  (re-derived, matches)")
    print(f"  records   {len(bound)} VERIFIED")
    for r in bound:
        print(f"    seq {r['seq']}  {r.get('checkpoint_id', r.get('attestation_id','?'))}  {r['record_sha256']}")

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
    wkeys = {h: keypairs(work / "keys", h.replace(".", "-")) for h in complete}
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

    for r in sorted(bound, key=lambda x: x["seq"]):
        blob = external_record_blob(r["seq"], system_id, bytes.fromhex(r["record_sha256"]),
                                    q, b0_hash, session_id)
        blobs.append(blob)
        (work / f"binding-blob-{r['seq']}.cbor").write_bytes(blob)

    prev = SignedCheckpoint.from_obj(
        cbor.loads((ROOT / a.prev_work / "checkpoint.cbor").read_bytes()))
    if prev.unsigned.epoch != a.epoch - 1:
        raise SystemExit(f"{a.prev_work} is epoch {prev.unsigned.epoch}, not {a.epoch - 1}")
    cp = build_checkpoint(a.epoch, latest, f=1, previous=prev.record_commitment())
    scp = sign_checkpoint(cp, keypairs(work / "keys", "checkpoint"))
    commitment = scp.record_commitment()
    payload = anchor_payload(cp.epoch, commitment.sha256, commitment.shake384)

    for i, blob in enumerate(blobs):
        (work / f"blob{i:02d}.cbor").write_bytes(blob)
    (work / "history.cbor").write_bytes(cbor.dumps([s.as_obj() for s in history]))
    (work / "checkpoint.cbor").write_bytes(scp.canonical())
    (work / "payload.hex").write_text(payload.hex() + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({
        "epoch": cp.epoch, "system_id": system_id, "binding_tag": tag.hex(),
        "records": [{"seq": r["seq"], "id": r.get("checkpoint_id", r.get("attestation_id")),
                     "record_sha256": r["record_sha256"]} for r in bound],
        "witnesses": sorted(complete) + [f"{system_id} x{len(bound)}"],
        "previous_epoch": prev.unsigned.epoch,
        "checkpoint_sha256": commitment.sha256.hex(),
        "payload_hex": payload.hex(),
    }, indent=2))
    print(f"\n  Next: PAYLOAD_HEX=$(cat {a.work}/payload.hex) CORES=16 bash live/race.sh\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
