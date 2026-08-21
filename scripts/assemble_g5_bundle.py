#!/usr/bin/env python3
"""Assemble the epoch-3 (authenticated-witness) sandwich bundle."""
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
from ctp.bitcoin_jan09 import block_hash, extract_anchor_from_coinbase, parse_single_tx_block
from ctp.sandwich import SandwichBundle, verify_sandwich, era_expectation, parse_frame_origin


def main():
    work = ROOT / "live" / "g5-work"
    ch = json.loads((work / "challenge.json").read_text())
    payload = bytes.fromhex((work / "payload.hex").read_text().strip())
    history = [SignedObservation.from_obj(o) for o in cbor.loads((work / "history.cbor").read_bytes())]
    checkpoint = SignedCheckpoint.from_obj(cbor.loads((work / "checkpoint.cbor").read_bytes()))
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(), (ROOT / "INVARIANTS.md").read_bytes())
    blobs = [p.read_bytes() for p in sorted(work.glob("blob*.cbor"))]

    chain = fetch_chain()
    hashes = [block_hash(b[:80]) for b in chain]
    b0_idx = hashes.index(ch["b0_hash"])
    if b0_idx + 1 != ch["b0_height"]:
        raise SystemExit("B0 height mismatch")
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
        raise SystemExit("epoch-3 block C not found")

    origin_s = parse_frame_origin(history[0].unsigned.reference_frame)
    cp = checkpoint.unsigned
    bundle = SandwichBundle(
        b0_raw=bytes.fromhex(ch["b0_raw_hex"]), b0_height=ch["b0_height"],
        session_id=bytes.fromhex(ch["session_id"]), evidence=blobs, history=history,
        checkpoint=checkpoint, block_c_raw=chain[c_idx],
        path_headers=[chain[i][:80] for i in range(b0_idx + 1, c_idx)],
        b1_headers=[chain[i][:80] for i in range(c_idx + 1, len(chain))],
        expectation=era_expectation(origin_s, (cp.interval.lower + cp.interval.upper) // 2),
        genesis=genesis, version=2, photo_manifest={}, prediction_json=b"")
    raw = bundle.canonical()
    dest = ROOT / "vectors" / "valid" / "roughtime-sandwich-bundle.cbor"
    dest.write_bytes(raw)

    checks, verdict, facts = verify_sandwich(SandwichBundle.from_bytes(raw))
    report = {"bundle": str(dest.relative_to(ROOT)), "bytes": len(raw),
              "sha256": hashlib.sha256(raw).hexdigest(),
              "b0": {"hash": facts["b0_hash"], "height": facts["b0_height"]},
              "block_c": {"hash": facts["block_c_hash"], "height": c_idx + 1},
              "burial_depth": facts["burial_depth"], "witnesses": cp.witness_count,
              "checks": checks, "verdict": verdict}
    (ROOT / "reports" / "roughtime-sandwich-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    sys.exit(0 if verdict.startswith("SANDWICH_PASS") else 1)


if __name__ == "__main__":
    main()
