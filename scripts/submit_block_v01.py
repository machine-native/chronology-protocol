#!/usr/bin/env python3
"""Submit a locally verified mined block over the v0.1-era wire protocol.

Usage:
  python scripts/submit_block_v01.py HOST [PORT] [MINED_BLOCK_HEX_FILE]

Default port: 18026
Default block: reports/mined-block.hex

This script refuses a block whose local PoW is invalid. Successful transmission is NOT treated
as node acceptance; preserve the target node's logs/block index and an independent chain query.
"""
from pathlib import Path
import sys,json,time,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ctp.bitcoin_jan09 import block_hash,target_from_bits,parse_single_tx_block
from ctp.p2p_v01 import submit_block,DEFAULT_PORT

if len(sys.argv)<2 or len(sys.argv)>4:
    raise SystemExit(__doc__)
host=sys.argv[1]
port=int(sys.argv[2]) if len(sys.argv)>=3 else DEFAULT_PORT
path=Path(sys.argv[3]) if len(sys.argv)>=4 else ROOT/"reports"/"mined-block.hex"
raw=bytes.fromhex(path.read_text().strip())
header,tx=parse_single_tx_block(raw)
h=block_hash(header)
bits=int.from_bytes(header[72:76],"little")
if int(h,16)>target_from_bits(bits):
    raise SystemExit("refusing to submit: local PoW invalid")
events=submit_block(host,port,raw)
receipt={
    "host":host,"port":port,"block_hash":h,"raw_sha256":hashlib.sha256(raw).hexdigest(),
    "events":events,
    "status":"BLOCK_SENT_ACCEPTANCE_NOT_YET_PROVEN",
    "required_acceptance_evidence":[
        "unmodified node log showing block acceptance or block-index inclusion",
        "independent chain view showing the same block hash on the active chain"
    ]
}
out=ROOT/"reports"/f"submission-{int(time.time())}.json"
out.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt,indent=2))
