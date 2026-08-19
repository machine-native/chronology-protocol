#!/usr/bin/env python3
"""Standalone offline verifier for a reality-sandwich bundle.

Usage:
  python scripts/verify_sandwich.py [BUNDLE.cbor]

Needs no network. Needs OpenSSL 3.5+ only for the post-quantum signature checks.
Exit 0 iff the verdict is SANDWICH_PASS or SANDWICH_PASS_UNBURIED.
"""
from pathlib import Path
import sys, json, hashlib
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ctp.sandwich import SandwichBundle, verify_sandwich

path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "vectors" / "valid" / "reality-sandwich-bundle.cbor"
raw = path.read_bytes()
checks, verdict, facts = verify_sandwich(SandwichBundle.from_bytes(raw))
print(json.dumps({"bundle": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                  "facts": facts, "checks": checks, "verdict": verdict}, indent=2))
raise SystemExit(0 if verdict.startswith("SANDWICH_PASS") else 1)
