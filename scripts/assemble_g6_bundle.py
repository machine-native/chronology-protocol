#!/usr/bin/env python3
"""Assemble the epoch-4 (rolling-code optical) sandwich bundle.

Two differences from the epoch-2 and epoch-3 assemblers.

B0's RAW BYTES COME FROM THE CHAIN, NOT FROM challenge.json.
The earlier scripts read `b0_raw_hex` out of the session file.
start_optical_session.py does not write that field, and taking the bytes from the
re-fetched chain is the better source regardless: it is the network's copy of the
block, checked to hash to the `b0_hash` the session recorded, rather than a local
transcription trusted because it is local.

THE ROLLING EXPECTATION TRAVELS AS prediction_json.
SandwichBundle carries that field for a model expectation that is explicitly not
evidence -- epoch 2 used it for the astrolabe's predicted lunar position. The
per-frame code expectation is the same kind of object: derived from EXIF, which
is the camera's own assertion, and confirmed by a human looking at a photograph
rather than by any check this program can run. Putting it anywhere else would
imply the bundle had verified it.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_sandwich_bundle import fetch_chain
from ctp import cbor
from ctp.model import SignedObservation, SignedCheckpoint
from ctp.genesis import build_protocol_genesis
from ctp.bitcoin_jan09 import (block_hash, extract_anchor_from_coinbase,
                               parse_single_tx_block)
from ctp.sandwich import (SandwichBundle, verify_sandwich, era_expectation,
                          parse_frame_origin)

WORK = "live/g6-work"
DEST = "vectors/valid/rolling-code-sandwich-bundle.cbor"
REPORT = "reports/rolling-code-sandwich-verification.json"


def main():
    work = ROOT / WORK
    ch = json.loads((work / "challenge.json").read_text())
    payload = bytes.fromhex((work / "payload.hex").read_text().strip())
    history = [SignedObservation.from_obj(o)
               for o in cbor.loads((work / "history.cbor").read_bytes())]
    checkpoint = SignedCheckpoint.from_obj(
        cbor.loads((work / "checkpoint.cbor").read_bytes()))
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    blobs = [p.read_bytes() for p in sorted(work.glob("blob*.cbor"))]

    manifest = {k: bytes.fromhex(v) for k, v in
                json.loads((work / "photo-manifest.json").read_text()).items()}
    # Re-hash the files on disk. The manifest was written by run_g6.py; if a
    # frame has been touched since, the checkpoint already committed to the old
    # digest and the bundle would carry a manifest describing files that no
    # longer exist in that form.
    for name, digest in sorted(manifest.items()):
        actual = hashlib.sha256((work / "photos" / name).read_bytes()).digest()
        if actual != digest:
            raise SystemExit(
                f"{name} no longer matches the manifest the checkpoint committed "
                f"to.\n  manifest {digest.hex()}\n  on disk  {actual.hex()}\n"
                "The frame was modified after consolidation. Restore the "
                "original or re-run run_g6.py against the frames as they now "
                "stand -- but not both.")

    prediction = (work / "rolling-expectation.json").read_bytes()

    chain = fetch_chain()
    hashes = [block_hash(b[:80]) for b in chain]
    if ch["b0_hash"] not in hashes:
        raise SystemExit(f"B0 {ch['b0_hash']} is not on the chain that was "
                         "fetched; it may have been reorganised away")
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
        raise SystemExit(
            "no block after B0 carries the epoch-4 payload. Mine and submit the "
            "anchor first: PAYLOAD_HEX=$(cat live/g6-work/payload.hex) "
            "./live/race.sh")

    origin_s = parse_frame_origin(history[0].unsigned.reference_frame)
    cp = checkpoint.unsigned
    bundle = SandwichBundle(
        b0_raw=b0_raw, b0_height=ch["b0_height"],
        session_id=bytes.fromhex(ch["session_id"]), evidence=blobs,
        history=history, checkpoint=checkpoint, block_c_raw=chain[c_idx],
        path_headers=[chain[i][:80] for i in range(b0_idx + 1, c_idx)],
        b1_headers=[chain[i][:80] for i in range(c_idx + 1, len(chain))],
        expectation=era_expectation(origin_s,
                                    (cp.interval.lower + cp.interval.upper) // 2),
        genesis=genesis, version=2, photo_manifest=manifest,
        prediction_json=prediction)

    raw = bundle.canonical()
    dest = ROOT / DEST
    dest.write_bytes(raw)

    checks, verdict, facts = verify_sandwich(SandwichBundle.from_bytes(raw))
    rex = json.loads(prediction)
    report = {
        "bundle": str(dest.relative_to(ROOT)), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "b0": {"hash": facts["b0_hash"], "height": facts["b0_height"]},
        "block_c": {"hash": facts["block_c_hash"], "height": c_idx + 1},
        "burial_depth": facts["burial_depth"],
        "witnesses": cp.witness_count,
        "frames": len(manifest),
        "frames_showing_a_code": rex["assessment"]["frames_with_code"],
        "distinct_codes": rex["assessment"]["distinct_codes"],
        "code_span_seconds": rex["assessment"]["span_seconds"],
        "checks": checks, "verdict": verdict,
    }
    (ROOT / REPORT).write_text(json.dumps(report, indent=2) + "\n", newline="\n")
    print(json.dumps(report, indent=2))
    if facts["burial_depth"] == 0:
        print("\n  NOTE: burial depth 0. The anchor block is the tip and nothing "
              "is stacked\n  on it yet, so the upper bound is not closed. Verdict "
              "reflects that.\n", file=sys.stderr)
    sys.exit(0 if verdict.startswith("SANDWICH_PASS") else 1)


if __name__ == "__main__":
    main()
