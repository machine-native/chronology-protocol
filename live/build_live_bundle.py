#!/usr/bin/env python3
"""Produce the live-anchored evidence bundle.

Takes the sealed v0.1.0 bundle (whose candidate block was explicitly un-mined) and
replaces exactly two fields: the candidate block becomes the block actually mined and
accepted on the live laboratory chain at height 221, and the candidate median-time-past
becomes the value fetched from the live tip context that block was built against.
Every signature, observation, checkpoint, and payload byte stays sealed and untouched —
the checkpoint payload embedded in the mined coinbase is byte-identical to the sealed one,
which the verifier re-checks. Output verdict must be PASS with all checks true.
"""
from pathlib import Path
import hashlib, json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ctp.bundle import EvidenceBundle
from ctp.verify import verify_bundle

MTP = 1787122655   # pindexPrev(height 220) GetMedianTimePast, from live/anchor-evidence/live-template-height221.json

sealed = (ROOT / "vectors" / "valid" / "evidence-bundle.cbor").read_bytes()
b = EvidenceBundle.from_bytes(sealed)
mined = bytes.fromhex((ROOT / "live" / "anchor-evidence" / "mined-block-height221.hex").read_text().strip())
b.candidate_block = mined
b.candidate_median_time_past = MTP
out = b.canonical()
dest = ROOT / "vectors" / "valid" / "evidence-bundle-live-anchored.cbor"
dest.write_bytes(out)

checks, verdict = verify_bundle(b.history, b.checkpoint, b.candidate_block, b.candidate_median_time_past, b.genesis)
report = {
    "sealed_bundle_sha256": hashlib.sha256(sealed).hexdigest(),
    "live_bundle": str(dest.relative_to(ROOT)),
    "live_bundle_sha256": hashlib.sha256(out).hexdigest(),
    "anchored_block_hash": hashlib.sha256(hashlib.sha256(mined[:80]).digest()).digest()[::-1].hex(),
    "checks": checks,
    "verdict": verdict,
}
print(json.dumps(report, indent=2))
sys.exit(0 if verdict == "PASS" else 1)
