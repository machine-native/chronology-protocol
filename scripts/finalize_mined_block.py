#!/usr/bin/env python3
"""Finalize and verify a mined header against reports/live-template.json.

Usage:
  python scripts/finalize_mined_block.py HEADER_HEX [LIVE_TEMPLATE_JSON]

The supplied 80-byte header must retain the template's version, previous hash, Merkle root,
nTime and nBits; only nNonce may differ.  A valid proof-of-work is mandatory.
"""
from pathlib import Path
import json, sys, hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ctp.bitcoin_jan09 import block_hash,target_from_bits

if len(sys.argv) not in (2,3):
    raise SystemExit(__doc__)
header=bytes.fromhex(sys.argv[1])
if len(header)!=80:
    raise SystemExit("header must be exactly 80 bytes")
tp=Path(sys.argv[2]) if len(sys.argv)==3 else ROOT/"reports"/"live-template.json"
o=json.loads(tp.read_text())
old_header=bytes.fromhex(o["header_nonce0"])
if header[:76] != old_header[:76]:
    raise SystemExit("refusing: mined header changed fields other than nonce")
bits=int.from_bytes(header[72:76],"little")
h=block_hash(header)
if int(h,16)>target_from_bits(bits):
    raise SystemExit(f"invalid PoW: {h}")

raw0=bytes.fromhex(o["block_nonce0"])
raw=header+raw0[80:]
out=ROOT/"reports"/"mined-block.hex"
out.write_text(raw.hex()+"\n")
receipt={
    "template":str(tp),
    "block_hash":h,
    "nonce":int.from_bytes(header[76:80],"little"),
    "raw_block_bytes":len(raw),
    "raw_block_sha256":hashlib.sha256(raw).hexdigest(),
    "status":"MINED_LOCALLY_NOT_YET_NODE_ACCEPTED"
}
(ROOT/"reports"/"mined-block.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt,indent=2))
