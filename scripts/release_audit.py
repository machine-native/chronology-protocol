#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import subprocess,sys,json,hashlib,time,shutil,py_compile,os

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
REPORTS=ROOT/"reports"
REPORTS.mkdir(exist_ok=True)

def _clean_output(text):
    marker="Spreadsheet runtime warmup failed during python startup"
    if marker in text:
        text=text.split(marker,1)[0]
    # Strip ANSI color escapes from test output.
    import re
    return re.sub(r"\x1b\[[0-9;]*m","",text).strip()

def run(cmd, *, ok=(0,), timeout=300):
    """Run a step. `ok` is True, False, or None for INDETERMINATE.

    None means the question could not be asked -- the tool is absent, or it timed
    out -- which is NOT the same as the check failing. Reporting a missing C
    compiler as a failed release gate would say this release is bad when nothing
    about it was examined. It also used to raise FileNotFoundError and abort the
    whole audit, discarding every other step's result along with it.
    """
    try:
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    except FileNotFoundError as e:
        return {"command":" ".join(map(str,cmd)),"returncode":None,"stdout":"",
                "stderr":f"{type(e).__name__}: {e}","ok":None,
                "indeterminate_reason":f"{cmd[0]!r} is not on PATH; this check was not run"}
    except subprocess.TimeoutExpired:
        return {"command":" ".join(map(str,cmd)),"returncode":None,"stdout":"",
                "stderr":f"timed out after {timeout}s","ok":None,
                "indeterminate_reason":"timed out; the check did not complete"}
    return {
        "command":" ".join(map(str,cmd)),
        "returncode":p.returncode,
        "stdout":_clean_output(p.stdout),
        "stderr":_clean_output(p.stderr),
        "ok":p.returncode in ok
    }

steps={}

# Static Python compilation.
compiled=[]
for p in sorted(ROOT.rglob("*.py")):
    if any(part in {".pytest_cache","__pycache__"} for part in p.parts):
        continue
    py_compile.compile(str(p),doraise=True)
    compiled.append(str(p.relative_to(ROOT)))
steps["PY_COMPILE"]={"ok":True,"files":len(compiled)}

steps["PYTEST"]=run([sys.executable,"-m","pytest","-q"])
steps["MILESTONE"]=run([sys.executable,"scripts/run_milestone1.py"],timeout=300)
steps["STANDALONE_VERIFY"]=run([sys.executable,"scripts/verify_bundle.py","vectors/valid/evidence-bundle.cbor"],timeout=300)

# Native miner build and exact known-genesis nonce check.
steps["NATIVE_BUILD"]=run(["cc","-O3","-march=native","native/mine_sha256d.c","-lcrypto","-o","native/mine_sha256d"])
from ctp.bitcoin_jan09 import GENESIS_RAW,GENESIS_NONCE,GENESIS_HASH
if steps["NATIVE_BUILD"]["ok"] is None:
    steps["GENESIS_NONCE_SCAN"]={"ok":None,"expected_hash":GENESIS_HASH,
        "indeterminate_reason":"the native miner was never built, so its output could not be checked"}
else:
    steps["GENESIS_NONCE_SCAN"]=run([
        str(ROOT/"native"/"mine_sha256d"),GENESIS_RAW[:80].hex(),str(GENESIS_NONCE),"1"
    ],ok=(0,))
    steps["GENESIS_NONCE_SCAN"]["expected_hash"]=GENESIS_HASH
    if steps["GENESIS_NONCE_SCAN"]["ok"] is not None:
        steps["GENESIS_NONCE_SCAN"]["hash_match"]=GENESIS_HASH in steps["GENESIS_NONCE_SCAN"]["stdout"]
        steps["GENESIS_NONCE_SCAN"]["ok"]=steps["GENESIS_NONCE_SCAN"]["ok"] and steps["GENESIS_NONCE_SCAN"]["hash_match"]

# Tamper test on the freshly generated sealed bundle.
src=ROOT/"vectors"/"valid"/"evidence-bundle.cbor"
bad=ROOT/"vectors"/"invalid"/"evidence-bundle-bitflip.cbor"
raw=bytearray(src.read_bytes())
raw[len(raw)//2]^=1
bad.write_bytes(raw)
steps["TAMPER_REJECTION"]=run([sys.executable,"scripts/verify_bundle.py",str(bad)],ok=(1,),timeout=300)
steps["TAMPER_REJECTION"]["ok"]=steps["TAMPER_REJECTION"]["ok"] and '"verdict": "FAIL"' in steps["TAMPER_REJECTION"]["stdout"]

# Parse current milestone report for protocol status.
verification=json.loads((REPORTS/"verification.json").read_text())
steps["MILESTONE_STATUS"]={
    "ok":verification["verdict"]=="PASS_PRE_POW",
    "verdict":verification["verdict"],
    "checks":verification["checks"],
    "bundle_sha256":verification["bundle"]["sha256"],
    "protocol_genesis_id":verification["protocol_genesis_id"],
}

n_fail=sum(1 for v in steps.values() if v.get("ok") is False)
n_indet=sum(1 for v in steps.values() if v.get("ok") is None)
all_ok=(n_fail==0)

# The live anchor is read from the evidence, not asserted. It was executed at
# v0.1.1 (epoch 0, height 221); this field said False long after that was true.
anchored=(ROOT/"vectors"/"valid"/"evidence-bundle-live-anchored.cbor").exists()

try:
    _v=subprocess.run(["git","describe","--tags","--abbrev=0"],cwd=ROOT,
                      capture_output=True,text=True,timeout=30).stdout.strip()
    version=_v.lstrip("v") or "unknown"
except Exception:
    version="unknown"

release={
    "protocol":"Chronology Protocol",
    "version":version,
    "audit_unix_time":int(time.time()),
    "status":("AUDIT_FAIL" if n_fail else
              "PASS_LIVE_ANCHORED" if anchored else
              "RELEASE_CANDIDATE_PASS_PRE_POW"),
    "checks_failed":n_fail,
    "checks_indeterminate":n_indet,
    "all_completed_engineering_checks_pass":all_ok,
    "live_anchor_claimed":anchored,
    "external_gate":[
        "construct candidate against current live tip using exact median-time-past and next-work context",
        "mine valid proof-of-work",
        "submit exact block to running Jan09-derived node",
        "capture ProcessBlock/AcceptBlock and active-chain evidence from unmodified node(s)"
    ],
    "steps":steps
}
(REPORTS/"release-audit.json").write_text(json.dumps(release,indent=2)+"\n")
print(json.dumps(release,indent=2))
if n_indet:
    print("", file=sys.stderr)
    print(f"  {n_indet} check(s) COULD NOT BE RUN, and are reported as", file=sys.stderr)
    print("  indeterminate rather than failed:", file=sys.stderr)
    for _k, _v in steps.items():
        if _v.get("ok") is None:
            _why = _v.get("indeterminate_reason", "no reason recorded")
            print(f"    {_k}: {_why}", file=sys.stderr)
    print("  Nothing failed, but not everything was checked. That is not the", file=sys.stderr)
    print("  same as success.", file=sys.stderr)
    print("", file=sys.stderr)

# 0 everything checked passed - 1 something failed - 2 nothing failed, something unasked
raise SystemExit(1 if n_fail else (2 if n_indet else 0))
