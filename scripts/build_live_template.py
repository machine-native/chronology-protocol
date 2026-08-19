#!/usr/bin/env python3
"""Build a live-chain block template from an existing milestone report.

Usage:
  python scripts/build_live_template.py PREV_HASH MEDIAN_TIME_PAST NEXT_BITS_HEX N_TIME

Inputs must come from the target chain context:
- PREV_HASH: intended parent block hash
- MEDIAN_TIME_PAST: pindexPrev->GetMedianTimePast()
- NEXT_BITS_HEX: GetNextWorkRequired(pindexPrev)
- N_TIME: miner-selected header time; must be > MEDIAN_TIME_PAST

The receiving Jan09 node independently also enforces nTime <= GetAdjustedTime()+2 hours.
This program does not treat nTime as physical chronology evidence.
"""
from pathlib import Path
import sys,json,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ctp.bitcoin_jan09 import make_block

if len(sys.argv)!=5:
    raise SystemExit(__doc__)
prev=sys.argv[1]
mtp=int(sys.argv[2],0)
bits=int(sys.argv[3],0)
ntime=int(sys.argv[4],0)
if ntime<=mtp:
    raise SystemExit("nTime must be greater than pindexPrev->GetMedianTimePast()")
report=json.loads((ROOT/"reports"/"verification.json").read_text())
payload=bytes.fromhex(report["anchor"]["payload_hex"])
b=make_block(payload,prev,ntime,bits,nonce=0)
out={
    "prev_hash":prev,"median_time_past":mtp,"nTime":ntime,"bits":hex(bits),
    "historical_context_rule":"nTime > pindexPrev->GetMedianTimePast(); nBits == GetNextWorkRequired(pindexPrev)",
    "future_time_rule_note":"receiving node also requires nTime <= GetAdjustedTime()+2h",
    "txid":b["txid"],"merkle_internal":b["merkle_internal"].hex(),
    "header_nonce0":b["header"].hex(),"block_nonce0":b["raw"].hex()
}
(ROOT/"reports"/"live-template.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
