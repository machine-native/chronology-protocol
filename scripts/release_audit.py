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
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
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
steps["GENESIS_NONCE_SCAN"]=run([
    str(ROOT/"native"/"mine_sha256d"),GENESIS_RAW[:80].hex(),str(GENESIS_NONCE),"1"
],ok=(0,))
steps["GENESIS_NONCE_SCAN"]["expected_hash"]=GENESIS_HASH
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

all_ok=all(v.get("ok",False) for v in steps.values())
release={
    "protocol":"Chronology Protocol",
    "version":"0.1.0",
    "audit_unix_time":int(time.time()),
    "status":"RELEASE_CANDIDATE_PASS_PRE_POW" if all_ok else "AUDIT_FAIL",
    "all_completed_engineering_checks_pass":all_ok,
    "live_anchor_claimed":False,
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
raise SystemExit(0 if all_ok else 1)
