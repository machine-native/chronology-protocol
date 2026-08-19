#!/usr/bin/env python3
"""Build a live-chain block template carrying the sandwich (epoch-1) anchor payload.

Usage:
  python scripts/build_sandwich_template.py PREV_HASH MEDIAN_TIME_PAST NEXT_BITS_HEX N_TIME

Identical contract to build_live_template.py, but the payload comes from
live/sandwich-work/payload.hex (the epoch-1 checkpoint) instead of the sealed
epoch-0 report. Writes reports/live-template.json for finalize_mined_block.py.
"""
from pathlib import Path
import sys, json
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ctp.bitcoin_jan09 import make_block

if len(sys.argv) != 5:
    raise SystemExit(__doc__)
prev = sys.argv[1]
mtp = int(sys.argv[2], 0)
bits = int(sys.argv[3], 0)
ntime = int(sys.argv[4], 0)
if ntime <= mtp:
    raise SystemExit("nTime must be greater than pindexPrev->GetMedianTimePast()")
payload = bytes.fromhex((ROOT / "live" / "sandwich-work" / "payload.hex").read_text().strip())
b = make_block(payload, prev, ntime, bits, nonce=0)
out = {
    "prev_hash": prev, "median_time_past": mtp, "nTime": ntime, "bits": hex(bits),
    "payload_source": "live/sandwich-work/payload.hex (epoch-1 sandwich checkpoint)",
    "historical_context_rule": "nTime > pindexPrev->GetMedianTimePast(); nBits == GetNextWorkRequired(pindexPrev)",
    "future_time_rule_note": "receiving node also requires nTime <= GetAdjustedTime()+2h",
    "txid": b["txid"], "merkle_internal": b["merkle_internal"].hex(),
    "header_nonce0": b["header"].hex(), "block_nonce0": b["raw"].hex()
}
(ROOT / "reports" / "live-template.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: out[k] for k in ("prev_hash", "nTime", "txid", "header_nonce0")}, indent=2))
