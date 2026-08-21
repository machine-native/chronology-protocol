#!/usr/bin/env python3
"""Broadcast or receive anchor-chain blocks over a LoRa serial module.

Targets AT-command LoRa transceivers of the REYAX RYLR998/RYLR896 family: a
$15–20 module that presents as a USB/UART serial port and needs no firmware
work. Any module with a transparent AT `SEND`/`+RCV` interface will fit.

  send mode:    read blocks (hex, one per line, e.g. live/chain-blocks.hex),
                fragment each one (ctp/radio.py wire format, hex-encoded for the
                AT payload), broadcast every fragment, repeat the whole set on an
                interval. No back-channel exists or is needed: repetition is the
                redundancy, and receivers validate everything themselves.

  recv mode:    parse `+RCV=` lines, reassemble, validate proof-of-work, and
                append each accepted block to an output hex file — which
                `fetch_full_chain.py`-style linkage checking can then audit.

HONESTY NOTE: the fragmentation, reassembly, corruption/forgery rejection and
airtime math are fully unit-tested (tests/test_radio.py). The serial/AT paths in
THIS file are written to the RYLR998 datasheet but have NOT yet run against a
physical module — that is exactly the hardware step this profile is waiting on,
and this note is removed only when a real over-the-air transfer has happened.

Duty cycle: the sender enforces a configurable duty-cycle cap (default 1%,
the common 868 MHz limit; 433 MHz bands typically allow 10%). YOU are
responsible for the rules of your band, region, and licence class.

Usage:
  python scripts/radio_relay.py send --port COM7 [--file live/chain-blocks.hex]
                                     [--repeat 900] [--duty 0.01] [--tail 5]
  python scripts/radio_relay.py recv --port COM7 [--out received-blocks.hex]

Requires pyserial (`pip install pyserial`) — an optional dependency of this
tool only; nothing in verification needs it.
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.radio import fragment, Reassembler, pow_valid, airtime_estimate_s
from ctp.bitcoin_jan09 import block_hash

# RYLR998 AT payload is ASCII, max 240 chars; hex-encoding halves capacity.
AT_MTU = 120


def _serial(port: str, baud: int):
    try:
        import serial
    except ImportError:
        raise SystemExit("pyserial is required for the relay tool: pip install pyserial")
    return serial.Serial(port, baud, timeout=2)


def _at(ser, cmd: str) -> str:
    ser.write((cmd + "\r\n").encode())
    time.sleep(0.15)
    return ser.read_all().decode(errors="replace").strip()


def send(args):
    blocks = [bytes.fromhex(l) for l in Path(args.file).read_text().split()]
    if args.tail:
        blocks = blocks[-args.tail:]
    ser = _serial(args.port, args.baud)
    print(_at(ser, "AT"))                          # liveness
    print(_at(ser, f"AT+ADDRESS={args.address}"))
    print(_at(ser, f"AT+NETWORKID={args.network}"))
    all_frags = []
    for raw in blocks:
        all_frags += fragment(raw, mtu=AT_MTU)
    est = airtime_estimate_s(len(all_frags), sf=args.sf, payload_bytes=AT_MTU)
    min_period = est / args.duty
    period = max(args.repeat, min_period)
    print(f"{len(blocks)} block(s), {len(all_frags)} fragments, "
          f"~{est:.1f}s airtime per pass; duty {args.duty:.0%} -> "
          f"repeating every {period:.0f}s")
    while True:
        for frag in all_frags:
            payload = frag.hex().upper()
            resp = _at(ser, f"AT+SEND=0,{len(payload)},{payload}")
            if "+OK" not in resp:
                print(f"  send warning: {resp!r}")
            time.sleep(args.gap)
        print(f"pass complete at {time.strftime('%H:%M:%S')}; next in {period:.0f}s")
        if args.once:
            return
        time.sleep(period)


def recv(args):
    ser = _serial(args.port, args.baud)
    print(_at(ser, "AT"))
    print(_at(ser, f"AT+ADDRESS={args.address}"))
    print(_at(ser, f"AT+NETWORKID={args.network}"))
    out = Path(args.out)
    known = set()
    if out.is_file():
        known = {block_hash(bytes.fromhex(l)[:80]) for l in out.read_text().split()}
        print(f"resuming: {len(known)} block(s) already in {out}")
    r = Reassembler()
    buf = b""
    print("listening (ctrl-c to stop)…")
    while True:
        buf += ser.read(4096)
        while b"\r\n" in buf:
            line, buf = buf.split(b"\r\n", 1)
            text = line.decode(errors="replace")
            if not text.startswith("+RCV="):
                continue
            # +RCV=<addr>,<len>,<data>,<rssi>,<snr> — data itself contains no commas
            try:
                parts = text[5:].split(",")
                packet = bytes.fromhex(parts[2])
            except (IndexError, ValueError):
                continue
            raw = r.feed(packet)
            if raw is None:
                continue
            h = block_hash(raw[:80])
            if h in known:
                continue
            with out.open("a", newline="\n") as f:
                f.write(raw.hex() + "\n")
            known.add(h)
            print(f"ACCEPTED {h}  ({len(raw)} bytes, PoW verified) -> {out}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    for name in ("send", "recv"):
        s = sub.add_parser(name)
        s.add_argument("--port", required=True, help="serial port, e.g. COM7 or /dev/ttyUSB0")
        s.add_argument("--baud", type=int, default=115200)
        s.add_argument("--address", type=int, default=1 if name == "send" else 2)
        s.add_argument("--network", type=int, default=18)
        s.add_argument("--sf", type=int, default=9)
    sp = sub.choices["send"]
    sp.add_argument("--file", default=str(ROOT / "live" / "chain-blocks.hex"))
    sp.add_argument("--tail", type=int, default=5, help="broadcast only the newest N blocks (0 = all)")
    sp.add_argument("--repeat", type=float, default=900, help="minimum seconds between passes")
    sp.add_argument("--duty", type=float, default=0.01, help="duty-cycle cap (0.01 = 1%%)")
    sp.add_argument("--gap", type=float, default=0.6, help="seconds between fragments")
    sp.add_argument("--once", action="store_true", help="one pass, then exit")
    rp = sub.choices["recv"]
    rp.add_argument("--out", default="received-blocks.hex")
    args = p.parse_args()
    (send if args.mode == "send" else recv)(args)


if __name__ == "__main__":
    main()
