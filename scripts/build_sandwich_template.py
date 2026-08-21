#!/usr/bin/env python3
"""Build a live-chain block template carrying a sandwich-epoch anchor payload.

Usage:
  python scripts/build_sandwich_template.py PREV_HASH MEDIAN_TIME_PAST NEXT_BITS_HEX N_TIME PAYLOAD_HEX_FILE

Identical contract to build_live_template.py, but the payload comes from the named
acquisition run's payload.hex instead of the sealed epoch-0 report. The path is an
explicit argument on purpose: an earlier version read one hard-coded path, so
successive runs overwrote each other's payload files and left a stale epoch behind.
Writes reports/live-template.json for finalize_mined_block.py.
"""
from pathlib import Path
import sys, json
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ctp.bitcoin_jan09 import make_block

if len(sys.argv) != 6:
    raise SystemExit(__doc__)
prev = sys.argv[1]
mtp = int(sys.argv[2], 0)
bits = int(sys.argv[3], 0)
ntime = int(sys.argv[4], 0)
payload_file = Path(sys.argv[5])
if ntime <= mtp:
    raise SystemExit("nTime must be greater than pindexPrev->GetMedianTimePast()")
payload = bytes.fromhex(payload_file.read_text().strip())
b = make_block(payload, prev, ntime, bits, nonce=0)
out = {
    "prev_hash": prev, "median_time_past": mtp, "nTime": ntime, "bits": hex(bits),
    "payload_source": str(payload_file),
    "historical_context_rule": "nTime > pindexPrev->GetMedianTimePast(); nBits == GetNextWorkRequired(pindexPrev)",
    "future_time_rule_note": "receiving node also requires nTime <= GetAdjustedTime()+2h",
    "txid": b["txid"], "merkle_internal": b["merkle_internal"].hex(),
    "header_nonce0": b["header"].hex(), "block_nonce0": b["raw"].hex()
}
(ROOT / "reports" / "live-template.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: out[k] for k in ("prev_hash", "nTime", "txid", "header_nonce0")}, indent=2))
