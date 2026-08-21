#!/usr/bin/env python3
"""Reference implementation of the rolling challenge (CAMERA-PHOTO/v2 aid).

Must derive byte-identically what tools/rolling-code.html displays:

    code(slot) = SHA-256("CHRN-ROLL/v1:" + SEED16 + ":" + slot)[:6 bytes] hex, upper
    slot       = floor(unix_time / slot_seconds)

Modes:
  expected  print the codes for a UTC time range (what should be visible in
            frames whose EXIF falls in that range, +/- 1 slot tolerance)
  show      live display in the terminal (for cross-checking a phone side-by-side)

Usage:
  python scripts/rolling_code.py expected SEED16 "2026-08-25T15:20:00" "2026-08-25T15:24:00" [--slot 10]
  python scripts/rolling_code.py show SEED16 [--slot 10]
"""
from __future__ import annotations
import argparse, calendar, hashlib, sys, time

DOMAIN = "CHRN-ROLL/v1"


def code_for(seed16: str, slot: int) -> str:
    seed16 = seed16.strip().upper()
    if len(seed16) != 16 or any(c not in "0123456789ABCDEF" for c in seed16):
        raise ValueError("seed must be exactly 16 hex characters")
    msg = f"{DOMAIN}:{seed16}:{slot}".encode()
    return hashlib.sha256(msg).hexdigest()[:12].upper()


def parse_utc(s: str) -> int:
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%S"))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    e = sub.add_parser("expected")
    e.add_argument("seed")
    e.add_argument("start_utc")
    e.add_argument("end_utc")
    e.add_argument("--slot", type=int, default=10)
    s = sub.add_parser("show")
    s.add_argument("seed")
    s.add_argument("--slot", type=int, default=10)
    a = p.parse_args()

    if a.mode == "expected":
        t0, t1 = parse_utc(a.start_utc), parse_utc(a.end_utc)
        for slot in range(t0 // a.slot - 1, t1 // a.slot + 2):   # +/- 1 slot tolerance
            w0 = time.strftime("%H:%M:%S", time.gmtime(slot * a.slot))
            w1 = time.strftime("%H:%M:%S", time.gmtime((slot + 1) * a.slot - 1))
            print(f"slot {slot}  {w0}-{w1}Z  {code_for(a.seed, slot)}")
    else:
        try:
            while True:
                slot = int(time.time()) // a.slot
                print(f"\r{code_for(a.seed, slot)}   slot {slot}   ", end="", flush=True)
                time.sleep(0.2)
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
