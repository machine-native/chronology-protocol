#!/usr/bin/env python3
"""Standalone offline verifier for a reality-sandwich bundle.

Usage:
  python scripts/verify_sandwich.py [BUNDLE.cbor] [--photos DIR]

Needs no network. Needs OpenSSL 3.5+ only for the post-quantum signature checks.
With --photos, every file in a v2 bundle's photo manifest must exist in DIR and
hash to its recorded sha256 (S_PHOTO_FILES).
Exit 0 iff the verdict is SANDWICH_PASS or SANDWICH_PASS_UNBURIED.
"""
from pathlib import Path
import sys, json, hashlib
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ctp.sandwich import SandwichBundle, verify_sandwich

args = [a for a in sys.argv[1:] if not a.startswith("--")]
photos_dir = None
if "--photos" in sys.argv:
    photos_dir = Path(sys.argv[sys.argv.index("--photos") + 1])
path = Path(args[0]) if args else ROOT / "vectors" / "valid" / "reality-sandwich-bundle.cbor"
raw = path.read_bytes()
b = SandwichBundle.from_bytes(raw)
checks, verdict, facts = verify_sandwich(b)
if photos_dir is not None and b.version >= 2:
    ok = bool(b.photo_manifest)
    for name, digest in (b.photo_manifest or {}).items():
        f = photos_dir / name
        ok = ok and f.is_file() and hashlib.sha256(f.read_bytes()).digest() == digest
    checks["S_PHOTO_FILES"] = ok
    if not ok and verdict.startswith("SANDWICH_PASS"):
        verdict = "FAIL"

def _explain(verdict):
    if verdict == "INDETERMINATE_TOOLCHAIN":
        import sys as _s
        print("", file=_s.stderr)
        print("*** NOT A FAILURE OF THE EVIDENCE ***", file=_s.stderr)
        print("Checks marked UNAVAILABLE could not be performed on this machine:", file=_s.stderr)
        print("your OpenSSL cannot verify ML-DSA-87 / SLH-DSA-SHAKE-256s (needs 3.5+).", file=_s.stderr)
        print("The signatures are UNKNOWN here, not invalid. Install OpenSSL 3.5+ and", file=_s.stderr)
        print("re-run to obtain a real verdict. See VERIFY.md section 0.", file=_s.stderr)

print(json.dumps({"bundle": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                  "facts": facts, "checks": checks, "verdict": verdict}, indent=2))
_explain(verdict)
raise SystemExit(0 if verdict.startswith("SANDWICH_PASS") else (2 if verdict=="INDETERMINATE_TOOLCHAIN" else 1))
