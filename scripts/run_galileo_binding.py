#!/usr/bin/env python3
"""Epoch 8: bind a Galileo satellite-signal capture into a reality sandwich.

Epochs 5-7 bound records that carry the session's binding tag, so each record is
bounded on both sides by this protocol alone: after B0 because it contains a
value derived from B0, before B1 because the anchored checkpoint commits to its
digest. A Galileo capture cannot carry the tag. Its bytes are what the satellites
broadcast, and nothing a receiver adds to them is evidence of anything.

It does not need to. Galileo's navigation-message authentication (OSNMA) releases
TESLA chain keys that were secret until their 30-second sub-frame, and the chain
is signed under a published trust anchor. A capture containing a verified key was
assembled no earlier than that key's release, whoever recorded it. So the capture
brings its own lower bound, from outside this protocol, and the sandwich supplies
the upper one:

    Galileo key release  <  capture  <  anchor block C  (< burial blocks)

By this protocol's vocabulary the binding is UPPER_ONLY, and that is the correct
verdict here: verify_binding reports what this protocol can show. The Galileo
half is checked by the code that owns it, time-witness (tw.galileo_binding), and
the two together give the bracket.

THE ORDER OF OPERATIONS
-----------------------
    --open   fetch a fresh B0 and fix the session (challenge.json)
    capture  record Galileo pages AFTER B0, for at least 16 minutes so the
             capture contains a signed DSM-KROOT (time-witness:
             scripts/capture_galmon.py --minutes 16 --out ...)
    --close  commit the capture's SHA-256 as an EXTERNAL-RECORD/v1 blob, run the
             NTP witnesses on the same challenge, build and sign the checkpoint
             chained to epoch 7, and write the anchor payload

Capturing after B0 is not needed for the Galileo bound, which holds on its own;
it keeps the session honest, so that every part of the epoch happened inside
its own window.

Usage:
    python scripts/run_galileo_binding.py --open
    python scripts/run_galileo_binding.py --close CAPTURE_FILE
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_sandwich import HOSTS, keypairs
from ctp import cbor
from ctp.binding import external_record_blob
from ctp.genesis import build_protocol_genesis
from ctp.model import (SignedCheckpoint, build_checkpoint, sign_checkpoint,
                       sign_observation)
from ctp.bitcoin_jan09 import anchor_payload
from ctp.pq import ensure_available
from ctp.sandwich import (challenge, exchange_nonce, ntp_exchange,
                          derive_measurement, evidence_blob, ntp_unsigned)

EPOCH = 8
PREV_WORK = "live/pm2-bind-work"            # epoch 7
SYSTEM_ID = "GALILEO-E1B-CAPTURE"
CAPTURE_NAME = "galileo-capture.bert"


def fetch_tip():
    r = subprocess.run([sys.executable, str(ROOT / "live" / "fetch_tip_context.py"),
                        "bitcoin.bitcoin-lab.org", "18026"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit("could not reach the chain; a binding needs a fresh B0")
    return json.loads((ROOT / "live" / "tip-context.json").read_text())


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def open_session(work: Path):
    ch_path = work / "challenge.json"
    if ch_path.exists():
        raise SystemExit(f"{ch_path} exists; use a new --work directory")
    ctx = fetch_tip()
    session_id = os.urandom(32)
    q = challenge(ctx["tip_hash"], session_id)
    work.mkdir(parents=True, exist_ok=True)
    ch_path.write_text(json.dumps({
        "b0_hash": ctx["tip_hash"], "b0_height": ctx["tip_height"],
        "session_id": session_id.hex(), "challenge": q.hex(),
        "system_id": SYSTEM_ID,
        "lower_bound_source": "Galileo OSNMA key release inside the record "
                              "(checked by time-witness); the record cannot "
                              "carry a binding tag",
        "issued_utc": utc(),
    }, indent=2) + "\n", newline="\n")
    print(f"B0 height {ctx['tip_height']}  {ctx['tip_hash']}")
    print(f"challenge {q.hex()}")
    print(f"\nNow capture Galileo pages (>= 16 min), then:\n"
          f"  python scripts/run_galileo_binding.py --work {work.relative_to(ROOT).as_posix()} "
          f"--close <capture>")


def close_session(work: Path, capture: Path):
    ch = json.loads((work / "challenge.json").read_text())
    if (work / "checkpoint.cbor").exists():
        raise SystemExit(f"{work} already has a checkpoint")
    q = bytes.fromhex(ch["challenge"])
    b0_hash = ch["b0_hash"]
    session_id = bytes.fromhex(ch["session_id"])

    record = capture.read_bytes()
    record_sha = hashlib.sha256(record).digest()
    (work / CAPTURE_NAME).write_bytes(record)
    print(f"capture {len(record)} bytes, sha256 {record_sha.hex()}")

    ensure_available()
    origin_s = (int(time.time()) // 86400) * 86400
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()

    print("\nNTP round on the same challenge:")
    exchanges = {}
    for seq in (0, 1):
        for host in HOSTS:
            if seq == 1 and host not in exchanges:
                continue
            nonce = exchange_nonce(q, host, seq)
            try:
                ex = ntp_exchange(host, nonce)
            except Exception as e:
                print(f"  {host} seq {seq}: FAILED ({e})")
                exchanges.pop(host, None)
                continue
            if ex["response"][24:32] != nonce:
                exchanges.pop(host, None)
                continue
            meas = derive_measurement(ex)
            exchanges.setdefault(host, {})[seq] = (
                ex, meas, evidence_blob(seq, ex, q, b0_hash, session_id))
            print(f"  {host} seq {seq}: ok rtt {meas['rtt_ps']/1e9:.0f}ms")
    complete = {h: r for h, r in exchanges.items() if 0 in r and 1 in r}
    if len(complete) < 3:
        raise SystemExit("too few NTP witnesses")

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

    gal_blob = external_record_blob(0, SYSTEM_ID, record_sha, q, b0_hash, session_id)
    blobs.append(gal_blob)
    (work / "galileo-binding-blob.cbor").write_bytes(gal_blob)

    prev = SignedCheckpoint.from_obj(
        cbor.loads((ROOT / PREV_WORK / "checkpoint.cbor").read_bytes()))
    if prev.unsigned.epoch != EPOCH - 1:
        raise SystemExit(f"{PREV_WORK} is epoch {prev.unsigned.epoch}")
    cp = build_checkpoint(EPOCH, latest, f=1, previous=prev.record_commitment())
    scp = sign_checkpoint(cp, keypairs(work / "keys", "checkpoint"))
    commitment = scp.record_commitment()
    payload = anchor_payload(cp.epoch, commitment.sha256, commitment.shake384)

    for i, blob in enumerate(blobs):
        (work / f"blob{i:02d}.cbor").write_bytes(blob)
    (work / "history.cbor").write_bytes(cbor.dumps([s.as_obj() for s in history]))
    (work / "checkpoint.cbor").write_bytes(scp.canonical())
    (work / "payload.hex").write_text(payload.hex() + "\n", newline="\n")

    ch["record_sha256"] = record_sha.hex()
    ch["record_file"] = CAPTURE_NAME
    ch["closed_utc"] = utc()
    (work / "challenge.json").write_text(json.dumps(ch, indent=2) + "\n", newline="\n")

    print(json.dumps({
        "epoch": cp.epoch,
        "system_id": SYSTEM_ID,
        "record_sha256": record_sha.hex(),
        "witnesses": sorted(complete) + [f"{SYSTEM_ID} external record"],
        "verdict": cp.verdict,
        "checkpoint_sha256": commitment.sha256.hex(),
        "payload_hex": payload.hex(),
    }, indent=2))
    print("\nNext: mine C carrying this payload (live/race_sandwich.sh "
          f"{(work / 'payload.hex').relative_to(ROOT).as_posix()}).\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="live/galileo-bind-work")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--open", action="store_true")
    g.add_argument("--close", metavar="CAPTURE")
    a = ap.parse_args()
    work = ROOT / a.work
    if a.open:
        open_session(work)
    else:
        close_session(work, Path(a.close))


if __name__ == "__main__":
    main()
