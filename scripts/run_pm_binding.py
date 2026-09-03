#!/usr/bin/env python3
"""Bind a batch of real air measurements into a reality sandwich.

Epoch 5 bound a SATROOT namespace -- a record made of arithmetic. Epoch 6 bound a
record made of air: laser-scattering measurements of the particulate matter in a
room in New Delhi, with the challenge inside the batch that carries them.

Epoch 7 binds the same thing measured better. Two PMS7003 instead of one, so
`co-location` is a check that ran rather than a check that could not, and a
BME280 alongside them, so the record states the humidity the reading was taken
in -- which decides whether an optical PM measurement means what it says.

WHY THE ORDER IS FIXED

The session must be opened BEFORE the sensor is read, and this program enforces
that by doing them in that order in one process. The reason is the asymmetry the
whole construction rests on:

    the tag cannot be computed before B0 is mined
       so a batch CONTAINING the tag cannot have been assembled earlier
          -> lower bound

    the batch digest goes into the checkpoint, anchored in a later block
       so the batch existed before that block
          -> upper bound

Reading first and binding afterwards would give only the upper bound. A batch of
readings taken last year can be committed today; nothing in the numbers says
when air was measured. The lower bound has to be built in at acquisition, which
is why the tag is derived and printed before the fan is even read.

WHAT THIS DOES NOT ESTABLISH

That the readings are accurate. Neither sensor has met a reference instrument,
their stated uncertainty is the manufacturer's figure, and both calibration
records say `reference: NONE` and `drift_model: refuse`. Two units agreeing is
consistency, not accuracy -- the same model from the same batch would agree
perfectly while both being wrong -- so the verdict is INCOMPLETE and stays there
until a reference exists.

The claim is narrow and exact: THESE readings, hashed exactly as recorded, were
taken inside this causal window. Whether the numbers are right is a different
question, answered by calibration, and this project does not pretend to have
answered it.

Usage:
    python scripts/run_pm_binding.py --port COM8
    python scripts/run_pm_binding.py --port COM8 --dry-run

The acquisition should run SHORTLY BEFORE the anchor is mined. B0 is fixed the
moment the session opens, so a long gap between acquiring and mining widens the
upper bound: readings taken at 15:00 and anchored at 20:00 are bounded only to
that five-hour window, however tight the lower bound is.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
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

EPOCH = 7
PREV_WORK = "live/pm-bind-work"                # epoch 6
SINGLE_SENSOR = False                         # False = ESP32 bridge, True = one CP2102
SYSTEM_ID = "NANOPROOF-AIR/v1"
NPA = Path("C:/Users/Yoga/Desktop/workspace/vscode_workspace_machine-native-foundation/nanoproof-air")


def fetch_tip():
    r = subprocess.run([sys.executable, str(ROOT / "live" / "fetch_tip_context.py"),
                        "bitcoin.bitcoin-lab.org", "18026"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit("could not reach the chain; a binding needs a fresh B0")
    return json.loads((ROOT / "live" / "tip-context.json").read_text())


def acquire(port: str, q_hex: str, seconds: float, work: str):
    """Run the nanoproof-air reader with the challenge, so the tag is inside."""
    # Epoch 7 onward reads the ESP32 bridge: two PM sensors and a BME280 at
    # once, so the batch carries humidity and a co-location check alongside the
    # particulate readings. Epoch 6 used read_pms7003.py against a single sensor
    # on a CP2102; that path still works and is what --single selects.
    reader = "read_pms7003.py" if SINGLE_SENSOR else "read_bridge.py"
    cmd = [sys.executable, str(NPA / "scripts" / reader),
           "--port", port, "--seconds", str(seconds),
           "--challenge-hex", q_hex, "--work", work]
    r = subprocess.run(cmd, cwd=str(NPA), capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit("acquisition failed")
    line = [l for l in r.stdout.splitlines() if "BATCH_DIGEST" in l]
    if not line:
        raise SystemExit("the reader emitted no batch digest")
    return bytes.fromhex(line[0].split()[-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True)
    ap.add_argument("--seconds", type=float, default=150)
    ap.add_argument("--work", default="live/pm2-bind-work")
    ap.add_argument("--npa-work", default="live/pm2-bound")
    ap.add_argument("--dry-run", action="store_true",
                    help="open a session and acquire, but build no checkpoint")
    a = ap.parse_args()

    work = ROOT / a.work
    if (work / "challenge.json").exists() and not a.dry_run:
        raise SystemExit(f"{work}/challenge.json exists; use a new --work")

    ctx = fetch_tip()
    b0_hash, b0_height = ctx["tip_hash"], ctx["tip_height"]
    session_id = os.urandom(32)
    q = challenge(b0_hash, session_id)
    tag = binding_tag(q, SYSTEM_ID)

    print(f"\nB0 height {b0_height}")
    print(f"  b0        {b0_hash}")
    print(f"  challenge {q.hex()}")
    print(f"  tag       {tag.hex()}   ({SYSTEM_ID})")
    print(f"\nacquiring for {a.seconds:.0f}s -- the tag is fixed before the first frame\n")

    digest = acquire(a.port, q.hex(), a.seconds, a.npa_work)
    print(f"\n  batch digest {digest.hex()}")

    if a.dry_run:
        print("\n  dry run: session opened and air measured, no checkpoint built.\n")
        return

    ensure_available()
    work.mkdir(parents=True, exist_ok=True)
    (work / "challenge.json").write_text(json.dumps({
        "b0_hash": b0_hash, "b0_height": b0_height,
        "session_id": session_id.hex(), "challenge": q.hex(),
        "system_id": SYSTEM_ID, "binding_tag": tag.hex(),
        "batch_digest": digest.hex(),
        "acquisition": str(NPA / a.npa_work),
        "issued_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2) + "\n", newline="\n")

    origin_s = (int(time.time()) // 86400) * 86400
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()

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
                exchanges.pop(host, None)
                continue
            meas = derive_measurement(ex)
            exchanges.setdefault(host, {})[seq] = (
                ex, meas, evidence_blob(seq, ex, q, b0_hash, session_id))
            print(f"    {host} seq {seq}: ok rtt {meas['rtt_ps']/1e9:.0f}ms")
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

    pm_blob = external_record_blob(0, SYSTEM_ID, digest, q, b0_hash, session_id)
    blobs.append(pm_blob)
    (work / "pm-binding-blob.cbor").write_bytes(pm_blob)

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

    print(json.dumps({
        "epoch": cp.epoch,
        "system_id": SYSTEM_ID,
        "binding_tag": tag.hex(),
        "batch_digest": digest.hex(),
        "witnesses": sorted(complete) + ["NANOPROOF-AIR/v1 batch"],
        "checkpoint_sha256": commitment.sha256.hex(),
        "payload_hex": payload.hex(),
    }, indent=2))
    print("\n  Next: mine B1 carrying this payload.\n")


if __name__ == "__main__":
    main()
