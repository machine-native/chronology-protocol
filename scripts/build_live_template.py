#!/usr/bin/env python3
"""Build a live-chain block template from an existing milestone report.

Usage:
  python scripts/build_live_template.py PREV_HASH MEDIAN_TIME_PAST NEXT_BITS_HEX N_TIME [PAYLOAD_HEX]

PAYLOAD_HEX is the 96-byte anchor payload for the epoch being anchored, from that
session's payload.hex. Omit it and the payload comes from reports/verification.json
-- which is the SEALED v0.1.0 baseline and carries epoch 0. That default was
silently correct exactly once. Anchoring a stale epoch produces a block that
duplicates one already on the chain, which is the condition
tests/test_chain_claims.py exists to detect after the fact rather than before.

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

if len(sys.argv) not in (5,6):
    raise SystemExit(__doc__)
prev=sys.argv[1]
mtp=int(sys.argv[2],0)
bits=int(sys.argv[3],0)
ntime=int(sys.argv[4],0)
if ntime<=mtp:
    raise SystemExit("nTime must be greater than pindexPrev->GetMedianTimePast()")
if len(sys.argv)==6:
    payload=bytes.fromhex(sys.argv[5])
else:
    report=json.loads((ROOT/"reports"/"verification.json").read_text())
    payload=bytes.fromhex(report["anchor"]["payload_hex"])
    print("WARNING: no PAYLOAD_HEX given; using reports/verification.json, the "
          "sealed v0.1.0 baseline.", file=sys.stderr)
if len(payload)!=96:
    raise SystemExit(f"payload must be 96 bytes, got {len(payload)}")
if payload[:4]!=b"CHRN":
    raise SystemExit("payload does not start with the CHRN magic")
_epoch=int.from_bytes(payload[8:16],"big")
print(f"anchoring epoch {_epoch}", file=sys.stderr)
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
