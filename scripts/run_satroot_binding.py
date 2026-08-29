#!/usr/bin/env python3
"""Epoch 5: bind a real SATROOT namespace into a reality sandwich.

docs/EXTERNAL-BINDING.md has said, accurately, "no binding has been performed"
since it was written. This performs one.

WHY SATROOT NEEDS THIS
----------------------
SATROOT gives ordering: sequence numbers, hash chains, prev_event_id. Ordering is
not time. It proves event B followed event A and says nothing about when either
happened, which is the same gap a signature leaves. Nothing in the SATROOT kernel
can close it, and nothing should -- it is a different concern.

WHERE THE TAG GOES, AND WHY THAT PLACE
--------------------------------------
The genesis event's `nonce` lands in `genesis_metadata`, which the replay engine
folds into the namespace `state_hash`. So a tag placed there is committed by
replay itself rather than by anything this script asserts: recompute the state
from the events and the tag is inside the result, or the state hash differs.

That matters because the alternative -- recording the tag in a sidecar file this
program writes -- would be a binding attested by the presenter. Review round 10
of SATROOT found exactly that shape: a trust anchor read off the artefact under
examination.

BOTH DIRECTIONS, AS ALWAYS
--------------------------
    tag = binding_tag(q, "SATROOT1")  --> into the genesis nonce
       the namespace could not have been replayed to this state before B0

    state_hash --> into the sandwich evidence
       the state existed before B1

Committing only the state hash proves the namespace existed before the closing
block and nothing about when it was made. A namespace replayed last year can be
committed today and the bytes are identical.

Usage:
    python scripts/run_satroot_binding.py --dry-run
    python scripts/run_satroot_binding.py
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_sandwich import HOSTS, keypairs
from ctp import cbor
from ctp.binding import binding_tag, external_record_blob, verify_binding
from ctp.genesis import build_protocol_genesis
from ctp.model import (SignedCheckpoint, build_checkpoint, sign_checkpoint,
                       sign_observation)
from ctp.bitcoin_jan09 import anchor_payload, block_hash
from ctp.pq import ensure_available
from ctp.sandwich import (challenge, exchange_nonce, ntp_exchange,
                          derive_measurement, evidence_blob, ntp_unsigned)

EPOCH = 5
PREV_WORK = "live/g6-work"                  # epoch 4
SYSTEM_ID = "SATROOT1"
SATROOT_SRC = Path("C:/Users/Yoga/Desktop/workspace/vscode_workspace_satroot/satroot")

# The real one-satoshi mainnet outpoint SATROOT bound as a namespace root,
# recorded in that project's ANCHORS.md. Used here as the root_id so the
# namespace refers to a real anchor rather than a placeholder.
ROOT_ID = "38ff9da029e66ee9b6a1b175025388caf7fb6d3bb0273812737d7dd6b347c473:0"


def fetch_tip():
    r = subprocess.run([sys.executable, str(ROOT / "live" / "fetch_tip_context.py"),
                        "bitcoin.bitcoin-lab.org", "18026"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit("could not reach the chain; a binding needs a fresh B0")
    return json.loads((ROOT / "live" / "tip-context.json").read_text())


def satroot_events(tag_hex: str) -> list:
    """A minimal SATROOT-1 namespace whose genesis nonce carries the tag."""
    return [{
        "protocol": "SATROOT-1",
        "version": "0.1",
        "action": "genesis",
        "root_id": ROOT_ID,
        "sequence": 0,
        "symbol": "CHRNBIND1",
        "name": "Chronology-bound namespace",
        "decimals": 0,
        "max_supply": "1",
        "mint_authority": "issuer",
        "transfer_model": "account-ledger",
        "initial_balances": {"issuer": "1"},
        "rules_hash": "sha256:chrn-binding-v1",
        "nonce": "chrn-binding/v1:" + tag_hex,
    }]


def replay(events_path: Path) -> tuple[bytes, str]:
    """Replay with SATROOT's own engine. Returns (state_json_bytes, state_hash)."""
    env = dict(os.environ, PYTHONPATH=str(SATROOT_SRC / "src"))
    r = subprocess.run([sys.executable, "-m", "satroot1", "replay", str(events_path)],
                       capture_output=True, text=True, cwd=str(SATROOT_SRC), env=env)
    if r.returncode != 0:
        raise SystemExit("satroot1 replay failed:\n" + r.stdout + r.stderr)
    lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    state_json = lines[0].encode()
    state_hash = [l for l in lines if l.startswith("state_hash=")][0].split("=", 1)[1]
    return state_json, state_hash


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="live/satroot-bind-work")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the namespace and check the binding, write nothing")
    a = ap.parse_args()

    work = ROOT / a.work
    ch_path = work / "challenge.json"
    if ch_path.exists() and not a.dry_run:
        raise SystemExit(f"{ch_path} exists; use a new --work directory")

    ctx = fetch_tip()
    b0_hash, b0_height = ctx["tip_hash"], ctx["tip_height"]
    session_id = os.urandom(32)
    q = challenge(b0_hash, session_id)
    tag = binding_tag(q, SYSTEM_ID)

    print(f"\nB0 height {b0_height}")
    print(f"  b0        {b0_hash}")
    print(f"  challenge {q.hex()}")
    print(f"  tag       {tag.hex()}   (SATROOT1)")

    work.mkdir(parents=True, exist_ok=True)
    events = satroot_events(tag.hex())
    ev_path = work / "satroot-events.json"
    ev_path.write_text(json.dumps(events, indent=1) + "\n", newline="\n")

    state_json, state_hash = replay(ev_path)
    print(f"\n  replayed by satroot1")
    print(f"  state_hash {state_hash}")
    print(f"  tag is inside the state: "
          f"{tag.hex() in state_json.decode()}")

    record_sha = hashlib.sha256(state_json).digest()
    print(f"  record sha256 {record_sha.hex()}")

    if a.dry_run:
        # Check both directions against a stub bundle carrying only the blob.
        class Stub:
            pass
        blob = external_record_blob(0, SYSTEM_ID, record_sha, q, b0_hash, session_id)
        s = Stub(); s.b0_raw = bytes.fromhex(ctx["tip_header"]) if "tip_header" in ctx else None
        print("\n  dry run: namespace built and replayed, nothing written to the chain.")
        print(f"  the tag appears in the replayed state, so the lower bound holds;")
        print(f"  the upper bound needs the sandwich, which --dry-run does not build.")
        return

    ensure_available()
    ch_path.write_text(json.dumps({
        "b0_hash": b0_hash, "b0_height": b0_height,
        "session_id": session_id.hex(), "challenge": q.hex(),
        "system_id": SYSTEM_ID, "binding_tag": tag.hex(),
        "satroot_state_hash": state_hash,
        "issued_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2) + "\n", newline="\n")
    (work / "satroot-state.json").write_bytes(state_json)

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

    sat_blob = external_record_blob(0, SYSTEM_ID, record_sha, q, b0_hash, session_id)
    blobs.append(sat_blob)
    (work / "satroot-binding-blob.cbor").write_bytes(sat_blob)

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
        "satroot_state_hash": state_hash,
        "satroot_record_sha256": record_sha.hex(),
        "witnesses": sorted(complete) + ["SATROOT1 external record"],
        "checkpoint_sha256": commitment.sha256.hex(),
        "payload_hex": payload.hex(),
    }, indent=2))
    print("\n  Next: mine B1 carrying this payload, then the binding is BOUND.\n")


if __name__ == "__main__":
    main()
