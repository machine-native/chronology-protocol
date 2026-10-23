#!/usr/bin/env python3
"""Open an external-binding session: fix B0, mint q, derive the tag for one system id.

The first half of an external-record binding (docs/EXTERNAL-BINDING.md), split out
so it can be run on its own when the record is produced by another party and comes
back later. Epochs 5-9 ran both halves in one script because the record was local.
Epoch 10 and the delegation-log cadence are round trips: this opens, the external
system carries the tag inside its signed bytes, and run_*_binding.py closes.

    python scripts/open_binding_session.py --system-id NAXYTRA-DELEGATION-LOG/1 \
        --work live/naxytra-delegation-work

What leaves this machine: the binding tag only. q stays in challenge.json; a tag
asserted ABOUT a record binds nothing, and q is what the tag is derived from.

Refuses to overwrite an open session. A second B0 for the same tag would orphan
whatever the external system has already bound to the first.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ctp.binding import binding_tag
from ctp.sandwich import challenge


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system-id", required=True)
    ap.add_argument("--work", required=True, help="e.g. live/naxytra-delegation-work")
    ap.add_argument("--seed", default="bitcoin.bitcoin-lab.org")
    ap.add_argument("--port", default="18026")
    a = ap.parse_args()

    work = ROOT / a.work
    work.mkdir(parents=True, exist_ok=True)
    ch_path = work / "challenge.json"
    if ch_path.exists():
        print(f"  a session is already open in {a.work}; refusing to overwrite it")
        return 2

    r = subprocess.run([sys.executable, str(ROOT / "live" / "fetch_tip_context.py"),
                        a.seed, a.port], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print("  could not reach the chain; a binding needs a fresh B0")
        print("  " + (r.stderr or r.stdout)[-300:])
        return 2
    ctx = json.loads((ROOT / "live" / "tip-context.json").read_text(encoding="utf-8"))
    b0_hash, b0_height = ctx["tip_hash"], ctx["tip_height"]

    session_id = os.urandom(32)
    q = challenge(b0_hash, session_id)
    tag = binding_tag(q, a.system_id)

    rec = {
        "record_type": "external_binding_session",
        "system_id": a.system_id,
        "opened_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "b0_height": b0_height,
        "b0_hash": b0_hash,
        "session_id": session_id.hex(),
        "challenge": q.hex(),
        "binding_tag": tag.hex(),
        "what_crosses_to_the_external_system": "binding_tag only. q never leaves this record.",
        "what_the_external_system_returns": "the record's digest, verified here against the public source before binding",
    }
    ch_path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"\n  session opened   {a.work}/challenge.json")
    print(f"  system_id        {a.system_id}")
    print(f"  B0               height {b0_height}")
    print(f"                   {b0_hash}")
    print(f"  session_id       {session_id.hex()}")
    print(f"  binding_tag      {tag.hex()}   <- to the external system")
    print(f"  challenge q      (held)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
