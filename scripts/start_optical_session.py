#!/usr/bin/env python3
"""Open a rolling-code optical observation session (epoch 4 and later).

The reality sandwich needs a lower bound that no one could have anticipated:
a challenge derived from a block that did not exist until moments before the
photographs were taken. This program fetches the live chain tip, derives that
challenge, and prints the 16-character code to type into the phone.

    B0  (chain tip, fetched now)
      |
      v
    q = SHA-256(DOM || hash(B0) || session_id)
      |
      v
    SEED16 = first 16 hex of q      <- typed into tools/rolling-code.html
      |
      v
    the phone displays a code that changes every 10 seconds, photographed
    beside the sky target, so the frames are bounded BELOW by B0's existence

Why a rolling code rather than one handwritten value: a single code proves the
photograph was taken after B0 existed. A code that changes every ten seconds,
captured across several frames, additionally proves the frames were taken across
a span of real time rather than all at once from one screen. That is what
upgrades CAMERA-PHOTO/v1 (OPERATOR_ASSERTED) toward something a verifier can
check without taking the operator's word for the timing.

Usage:
  python scripts/start_optical_session.py --work live/g6-work
  python scripts/start_optical_session.py --work live/g6-work --host <seed> --port 18026
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.sandwich import challenge
from ctp.bitcoin_jan09 import block_hash


def fetch_tip(host: str, port: int):
    """Get the current tip by asking the chain, not by reading a cached file."""
    print(f"fetching the chain tip from {host}:{port} ...")
    r = subprocess.run([sys.executable, str(ROOT / "live" / "fetch_tip_context.py"),
                        host, str(port)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"could not reach the chain:\n{r.stdout}\n{r.stderr}\n\n"
                         "A session cannot be opened without a fresh B0 -- the whole\n"
                         "point is that the challenge could not have been known earlier.")
    ctx = json.loads((ROOT / "live" / "tip-context.json").read_text())
    return ctx


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True,
                    help="session directory, e.g. live/g6-work")
    ap.add_argument("--host", default="bitcoin.bitcoin-lab.org")
    ap.add_argument("--port", type=int, default=18026)
    ap.add_argument("--slot", type=int, default=10, help="seconds per code")
    a = ap.parse_args()

    work = Path(a.work)
    if (work / "challenge.json").exists():
        raise SystemExit(
            f"{work}/challenge.json already exists.\n"
            "Refusing to overwrite it: a session's challenge is the evidence that\n"
            "fixes its lower bound, and replacing it would silently invalidate any\n"
            "photographs already taken against it. Use a new --work directory.")

    ctx = fetch_tip(a.host, a.port)
    b0_hash = ctx["tip_hash"]
    b0_height = ctx["tip_height"]

    session_id = os.urandom(32)
    q = challenge(b0_hash, session_id)
    seed16 = q.hex()[:16].upper()

    work.mkdir(parents=True, exist_ok=True)
    (work / "challenge.json").write_text(json.dumps({
        "b0_hash": b0_hash,
        "b0_height": b0_height,
        "session_id": session_id.hex(),
        "challenge": q.hex(),
        "seed16": seed16,
        "slot_seconds": a.slot,
        "issued_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "SEED16 is the first 16 hex of the challenge, typed into "
                "tools/rolling-code.html. The challenge is bound to B0, so no code "
                "in these photographs could have been produced before B0 existed.",
    }, indent=2) + "\n", newline="\n")

    print(f"\n{'='*70}")
    print(f"  SESSION OPEN — B0 is height {b0_height}")
    print(f"{'='*70}\n")
    print(f"  B0 hash      {b0_hash}")
    print(f"  issued       {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"  written      {work}/challenge.json\n")
    print(f"  TYPE THIS INTO THE PHONE:      {seed16}")
    print(f"  slot length:                   {a.slot} seconds\n")
    print(f"{'='*70}")
    print("  NEXT, in order:")
    print(f"{'='*70}")
    print("   1. On this machine, serve the code page:")
    print("        cd tools && python -m http.server 8000")
    print("   2. On the phone (same wi-fi), open:")
    print("        http://<this-machine-ip>:8000/rolling-code.html")
    print(f"   3. Enter {seed16}, press Start. A large code appears and changes")
    print(f"      every {a.slot} seconds.")
    print("   4. Photograph the sky target WITH the phone screen in the same frame.")
    print("      At least 6 frames spanning at least 60 seconds, and the code must")
    print("      VISIBLY DIFFER between frames -- identical codes across every frame")
    print("      would prove only one instant, which is the thing being improved on.")
    print("   5. Copy the originals (do not edit, do not re-encode -- EXIF matters):")
    print(f"        {work}/photos/")
    print("   6. Check which codes should be visible, from the EXIF times:")
    print(f"        python scripts/rolling_code.py expected {seed16} \\")
    print("            \"<first-frame-UTC>\" \"<last-frame-UTC>\" --slot", a.slot)
    print("   7. Then run the acquisition to close the sandwich.\n")
    print("  The session is now OPEN. Nothing is proved until the photographs exist")
    print("  and a later block B1 closes the upper bound.\n")


if __name__ == "__main__":
    main()
