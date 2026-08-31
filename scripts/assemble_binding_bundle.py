#!/usr/bin/env python3
"""Assemble a sandwich bundle for an external-record binding epoch.

Epochs 5 and 6 differ from the optical epochs in what they bind, not in how.
Epoch 5 bound a SATROOT namespace; epoch 6 bound a batch of air measurements.
Both put the record's digest in an EXTERNAL-RECORD/v1 evidence blob and the
binding tag inside the record itself, so one assembler serves both and a third
binding needs no new code.

There is no photo manifest and no prediction, so these are version-1 bundles.
The binding is already in `evidence`; adding a second copy elsewhere would
invite a reader to check the wrong one.

WHY --b1-depth EXISTS
A bundle's digest changes every time the chain grows, because the trailing
headers grow with it. Freezing the depth is what lets a verifier re-run this
months later and obtain the digest that was published. Without it the published
number is unreproducible by construction, which is worse than having no number.

Usage:
    python scripts/assemble_binding_bundle.py --work live/satroot-bind-work \\
        --dest vectors/valid/satroot-binding-bundle.cbor \\
        --report reports/satroot-binding-verification.json
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_sandwich_bundle import fetch_chain
from ctp import cbor
from ctp.binding import PROFILE
from ctp.model import SignedObservation, SignedCheckpoint
from ctp.genesis import build_protocol_genesis
from ctp.bitcoin_jan09 import (block_hash, extract_anchor_from_coinbase,
                               parse_single_tx_block)
from ctp.sandwich import (SandwichBundle, verify_sandwich, era_expectation,
                          parse_frame_origin)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--b1-depth", type=int, default=None,
                    help="blocks after the anchor to include. Fixing it makes "
                         "the bundle reproducible; omit to take all available.")
    a = ap.parse_args()

    work = ROOT / a.work
    ch = json.loads((work / "challenge.json").read_text())
    payload = bytes.fromhex((work / "payload.hex").read_text().strip())
    history = [SignedObservation.from_obj(o)
               for o in cbor.loads((work / "history.cbor").read_bytes())]
    checkpoint = SignedCheckpoint.from_obj(
        cbor.loads((work / "checkpoint.cbor").read_bytes()))
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    blobs = [p.read_bytes() for p in sorted(work.glob("blob*.cbor"))]

    # The binding blob must be present and must be the one the checkpoint saw.
    # Assembling a "binding" bundle with no binding in it would produce a
    # perfectly valid sandwich that proves nothing about the external record.
    bound = [b for b in blobs
             if (lambda o: isinstance(o, dict) and o.get(1) == PROFILE)(cbor.loads(b))]
    if not bound:
        raise SystemExit(f"no {PROFILE} blob in {a.work}; this is not a binding "
                         "epoch, or the acquisition did not complete")
    binding = cbor.loads(bound[0])
    if binding[10] != bytes.fromhex(ch["challenge"]):
        raise SystemExit("the binding blob carries a different challenge than "
                         "challenge.json; they are not from the same session")

    chain = fetch_chain()
    hashes = [block_hash(b[:80]) for b in chain]
    if ch["b0_hash"] not in hashes:
        raise SystemExit(f"B0 {ch['b0_hash']} is not on the fetched chain; it may "
                         "have been reorganised away")
    b0_idx = hashes.index(ch["b0_hash"])
    if b0_idx + 1 != ch["b0_height"]:
        raise SystemExit(f"B0 height mismatch: session says {ch['b0_height']}, "
                         f"chain position says {b0_idx + 1}")
    b0_raw = chain[b0_idx]

    c_idx = None
    for i in range(b0_idx + 1, len(chain)):
        try:
            _, tx = parse_single_tx_block(chain[i])
            if extract_anchor_from_coinbase(tx)["payload"] == payload:
                c_idx = i
                break
        except Exception:
            continue
    if c_idx is None:
        raise SystemExit(f"no block after B0 carries this payload. Mine the "
                         f"anchor first:\n  PAYLOAD_HEX=$(cat {a.work}/payload.hex) "
                         "./live/race.sh")

    available = len(chain) - (c_idx + 1)
    if a.b1_depth is None:
        end = len(chain)
    else:
        if a.b1_depth > available:
            raise SystemExit(f"--b1-depth {a.b1_depth} requested but only "
                             f"{available} block(s) follow the anchor")
        end = c_idx + 1 + a.b1_depth
    b1_headers = [chain[i][:80] for i in range(c_idx + 1, end)]

    origin_s = parse_frame_origin(history[0].unsigned.reference_frame)
    cp = checkpoint.unsigned

    # An ERA expectation is computed AT AN INSTANT. When the witnesses failed to
    # agree there is no such instant, and inventing one -- by averaging the
    # conflicting intervals, say -- would manufacture exactly the agreement the
    # consensus refused to assert. Epoch 5 is this case: five NTP witnesses whose
    # lower bounds spanned 1.55 s with intervals under 0.51 s wide, so no three
    # could overlap and the checkpoint carries TIME_CONFLICT.
    #
    # verify_sandwich already gates its ERA check on the interval existing, so a
    # marker here is checked by nobody and misleads nobody.
    if cp.interval is None:
        expectation = {1: "NO-CONSENSUS-INTERVAL/v1",
                       2: cp.verdict,
                       3: "the witnesses did not agree on a time interval, so no "
                          "instant exists at which to state an Earth Rotation "
                          "Angle. The causal bound B0 < record < B1 does not "
                          "depend on this and is unaffected."}
    else:
        expectation = era_expectation(
            origin_s, (cp.interval.lower + cp.interval.upper) // 2)

    bundle = SandwichBundle(
        b0_raw=b0_raw, b0_height=ch["b0_height"],
        session_id=bytes.fromhex(ch["session_id"]), evidence=blobs,
        history=history, checkpoint=checkpoint, block_c_raw=chain[c_idx],
        path_headers=[chain[i][:80] for i in range(b0_idx + 1, c_idx)],
        b1_headers=b1_headers,
        expectation=expectation,
        genesis=genesis, version=1)

    raw = bundle.canonical()
    dest = ROOT / a.dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)

    checks, verdict, facts = verify_sandwich(SandwichBundle.from_bytes(raw))
    report = {
        "bundle": str(dest.relative_to(ROOT)), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "epoch": cp.epoch,
        "bound_system": binding[2],
        "bound_record_sha256": binding[3].hex(),
        "binding_tag": binding[4].hex(),
        "b0": {"hash": facts["b0_hash"], "height": facts["b0_height"]},
        "block_c": {"hash": facts["block_c_hash"], "height": c_idx + 1},
        "burial_depth": facts["burial_depth"],
        "b1_depth_frozen_at": len(b1_headers),
        "reproduce": (f"python scripts/assemble_binding_bundle.py --work {a.work} "
                      f"--dest {a.dest} --report {a.report} "
                      f"--b1-depth {len(b1_headers)}"),
        "witnesses": cp.witness_count,
        "checkpoint_verdict": cp.verdict,
        "consensus_interval": (None if cp.interval is None
                               else [cp.interval.lower, cp.interval.upper]),
        "checks": checks, "verdict": verdict,
        "note": "the sandwich bounds the record's DIGEST in time. Whether the "
                "record itself is meaningful is the originating system's "
                "question, not this one's.",
    }
    (ROOT / a.report).write_text(json.dumps(report, indent=2) + "\n", newline="\n")
    print(json.dumps(report, indent=2))
    if facts["burial_depth"] == 0:
        print("\n  NOTE: burial depth 0 -- the anchor is the tip, nothing is "
              "stacked on it,\n  so the upper bound is not closed yet.\n",
              file=sys.stderr)
    sys.exit(0 if verdict.startswith("SANDWICH_PASS") else 1)


if __name__ == "__main__":
    main()
