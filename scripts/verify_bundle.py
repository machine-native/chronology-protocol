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

def _explain(verdict):
    if verdict == "INDETERMINATE_TOOLCHAIN":
        import sys as _s
        print("", file=_s.stderr)
        print("*** NOT A FAILURE OF THE EVIDENCE ***", file=_s.stderr)
        print("Checks marked UNAVAILABLE could not be performed on this machine:", file=_s.stderr)
        print("your OpenSSL cannot verify ML-DSA-87 / SLH-DSA-SHAKE-256s (needs 3.5+).", file=_s.stderr)
        print("The signatures are UNKNOWN here, not invalid. Install OpenSSL 3.5+ and", file=_s.stderr)
        print("re-run to obtain a real verdict. See VERIFY.md section 0.", file=_s.stderr)

out={"bundle":str(path),"sha256":hashlib.sha256(raw).hexdigest(),"checks":checks,"verdict":verdict}
print(json.dumps(out,indent=2))
_explain(verdict)
raise SystemExit(0 if verdict in ("PASS","PASS_PRE_POW") else (2 if verdict=="INDETERMINATE_TOOLCHAIN" else 1))
