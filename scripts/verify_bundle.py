#!/usr/bin/env python3
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ctp.bundle import EvidenceBundle
from ctp.verify import verify_bundle

path=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"vectors"/"valid"/"evidence-bundle.cbor"
raw=path.read_bytes()
b=EvidenceBundle.from_bytes(raw)
checks,verdict=verify_bundle(b.history,b.checkpoint,b.candidate_block,b.candidate_median_time_past,b.genesis)
out={"bundle":str(path),"sha256":hashlib.sha256(raw).hexdigest(),"checks":checks,"verdict":verdict}
print(json.dumps(out,indent=2))
raise SystemExit(0 if verdict in ("PASS","PASS_PRE_POW") else 1)
