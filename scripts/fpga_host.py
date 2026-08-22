#!/usr/bin/env python3
"""Host driver for the FPGA nonce scanner.

Sends work, receives candidates, and — importantly — applies the EXACT target test
itself. The FPGA only coarse-filters; validity is decided here, by the same code
path that validates real blocks. A hardware bug can waste work or miss a candidate;
it cannot make an invalid block look valid.

Modes:
  ping      confirm the link
  selftest  replay work whose answer is already known from the live chain, and
            require the board to return that exact nonce (the honest bring-up test)
  mine      scan for a real block on top of the current chain tip

Usage:
  python scripts/fpga_host.py ping --port COM7
  python scripts/fpga_host.py selftest --port COM7
  python scripts/fpga_host.py mine --port COM7 --payload live/g5-work/payload.hex

Requires pyserial (`pip install pyserial`) — needed only for this tool.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.bitcoin_jan09 import block_hash, target_from_bits

IV = [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
      0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19]
K = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
     0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
     0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
     0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
     0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
     0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
     0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
     0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]
M32 = 0xFFFFFFFF


def _rotr(x, n): return ((x >> n) | (x << (32 - n))) & M32


def compress(state, block):
    w = list(struct.unpack(">16I", block))
    for t in range(16, 64):
        s0 = _rotr(w[t-15], 7) ^ _rotr(w[t-15], 18) ^ (w[t-15] >> 3)
        s1 = _rotr(w[t-2], 17) ^ _rotr(w[t-2], 19) ^ (w[t-2] >> 10)
        w.append((w[t-16] + s0 + w[t-7] + s1) & M32)
    a, b, c, d, e, f, g, h = state
    for t in range(64):
        t1 = (h + (_rotr(e,6)^_rotr(e,11)^_rotr(e,25)) + ((e & f) ^ (~e & M32 & g)) + K[t] + w[t]) & M32
        t2 = ((_rotr(a,2)^_rotr(a,13)^_rotr(a,22)) + ((a & b) ^ (a & c) ^ (b & c))) & M32
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & M32, c, b, a, (t1 + t2) & M32
    return [(x + y) & M32 for x, y in zip(state, [a, b, c, d, e, f, g, h])]


def make_work(header80: bytes) -> bytes:
    """'W' + midstate(32) + tail(12) + nonce_start(4), all big-endian."""
    mid = compress(IV, header80[:64])
    return b"W" + b"".join(struct.pack(">I", x) for x in mid) + header80[64:76]


def open_port(port, baud=115200):
    try:
        import serial
    except ImportError:
        raise SystemExit("pyserial required: pip install pyserial")
    return serial.Serial(port, baud, timeout=1)


def ping(ser) -> bool:
    ser.reset_input_buffer()
    ser.write(b"P")
    return ser.read(1) == b"K"


def scan(ser, header80: bytes, nonce_start: int, bits: int, timeout_s: float):
    """Send work, wait for a candidate, verify it here against the exact target."""
    ser.reset_input_buffer()
    ser.write(make_work(header80) + struct.pack(">I", nonce_start))
    target = target_from_bits(bits)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        tag = ser.read(1)
        if not tag:
            continue
        if tag == b"E":
            return None, "exhausted"
        if tag != b"F":
            continue
        body = ser.read(36)
        if len(body) != 36:
            return None, "short report"
        nonce = struct.unpack(">I", body[:4])[0]
        # authority stays here: rebuild the header and check the real rule
        cand = header80[:76] + struct.pack("<I", nonce)
        h = block_hash(cand)
        if int(h, 16) <= target:
            return (nonce, h, cand), "valid"
        return (nonce, h, cand), "filtered-but-below-target=False"
    return None, "timeout"


def cmd_ping(a):
    ser = open_port(a.port, a.baud)
    print("link OK" if ping(ser) else "no response — check port, wiring and bitstream")


def cmd_selftest(a):
    """Replay work whose answer the live chain already proved.

    --depth sets how many nonces before the known answer the scan starts. The
    default of 4 is the shallowest useful check: it proves the board computes
    SHA-256d correctly and reports over UART, but it barely exercises the nonce
    scanner at all. A deep run is a far stronger claim -- the board must walk a
    long range, reject every wrong nonce, and stop on exactly the right one --
    and it doubles as the throughput measurement, since the elapsed time is over
    a known number of nonces.
    """
    vecs = json.loads((ROOT / "fpga" / "sim" / "golden-vectors.json").read_text())
    v = vecs[0]
    hdr = bytes.fromhex(v["header_hex"])
    ser = open_port(a.port, a.baud)
    if not ping(ser):
        raise SystemExit("no link")
    depth = max(1, a.depth)
    start = (v["nonce"] - depth + 1) & M32
    span = depth
    print(f"replaying height {v['height']}: expecting nonce {v['nonce']}")
    if depth > 1000:
        print(f"scanning {span:,} nonces up to it — the board must reject every "
              f"one of the first {span-1:,}")
    t0 = time.time()
    got, status = scan(ser, hdr, start, int(v["bits"], 16), a.timeout)
    dt = time.time() - t0
    if got and got[0] == v["nonce"] and got[1] == v["hash"]:
        print(f"SELFTEST PASS — board returned nonce {got[0]} and hash {got[1]}")
        print(f"  ({dt:.2f}s for {span:,} nonces)")
        if span >= 100_000 and dt > 0:
            rate = span / dt / 1e6
            print(f"  measured rate: {rate:.4f} MH/s")
            print(f"  full 2^32 sweep at this rate: {2**32/(rate*1e6)/3600:.1f} hours")
        elif span < 100_000:
            print("  too few nonces to measure a rate; use --depth 1000000")
    else:
        print(f"SELFTEST FAIL — status {status}, got {got}")
        sys.exit(1)


def cmd_mine(a):
    # The board passed selftest on real hardware on 2026-08-22, so the original
    # precondition is met. What blocks this now is simply that the mode is not
    # written: it needs live chain-tip fetching, coinbase construction and block
    # submission, none of which exist here yet.
    #
    # There is also no hurry. The board as built runs at roughly 0.09 MH/s
    # against this laptop's measured 4.0 MH/s, so it would lose every race it
    # entered. It becomes worth wiring up after the MMCM and multi-core work,
    # or for continuous low-power mining where always-on beats fast-but-rarely.
    raise SystemExit(
        "mine mode is not implemented yet.\n"
        "  selftest has passed on hardware, so the safety precondition is met;\n"
        "  what is missing is chain-tip fetch, coinbase build and submission.\n"
        "  Use live/race_sandwich.sh for CPU mining meanwhile.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    for name, fn in (("ping", cmd_ping), ("selftest", cmd_selftest), ("mine", cmd_mine)):
        s = sub.add_parser(name)
        s.add_argument("--port", required=True)
        s.add_argument("--baud", type=int, default=115200)
        s.add_argument("--timeout", type=float, default=120)
        if name == "selftest":
            s.add_argument("--depth", type=int, default=4,
                           help="nonces to scan before the known answer. 4 checks "
                                "the hash only; 1000000 exercises the scanner and "
                                "measures the real hash rate.")
        s.set_defaults(func=fn)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
