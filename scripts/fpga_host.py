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
  python scripts/fpga_host.py ping --port COM4
  python scripts/fpga_host.py selftest --port COM4 --depth 20000000
  python scripts/fpga_host.py mine --port COM4 --refresh

Mining never broadcasts on its own. A found block is written to live/mine/ and
sent only by scripts/submit_block.py, or by passing --submit explicitly. Mining a
wrong block costs a file; publishing one costs a chain that does not forget.

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


def scan(ser, header80: bytes, nonce_start: int, bits: int, timeout_s: float,
         progress=False):
    """Send work, wait for a candidate, verify it here against the exact target.

    A deep scan means many seconds in which neither side transmits anything. On
    Windows an idle FTDI can be suspended out from under an open handle, and the
    next read fails with `ClearCommError ... Access is denied` -- observed here
    on 2026-08-22 during a one-million-nonce scan that had already pinged
    successfully.

    So the link is kept warm: a 'P' ping every second, whose 'K' reply is
    ignored by the tag loop below. This is safe during a scan -- the RTL treats
    only 'W' as work and only 'S' as abort, and answers a ping whenever it is
    not already transmitting a report -- and it gives the operator a sign of
    life during a long run.
    """
    ser.reset_input_buffer()
    ser.write(make_work(header80) + struct.pack(">I", nonce_start))
    target = target_from_bits(bits)
    started = time.time()
    deadline = started + timeout_s
    last_poke = started
    while time.time() < deadline:
        try:
            tag = ser.read(1)
        except Exception as e:                       # the port went away
            return None, f"serial-error: {e}"
        if not tag:
            now = time.time()
            if now - last_poke >= 1.0:
                try:
                    ser.write(b"P")
                except Exception as e:
                    return None, f"serial-error: {e}"
                last_poke = now
                if progress:
                    # trailing spaces clear whatever a longer previous line left
                    print(f"\r  scanning… {now-started:7.1f}s   ", end="", flush=True)
            continue
        if tag in (b"K", b"\x00"):       # keepalive echo, or line noise
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
    got, status = scan(ser, hdr, start, int(v["bits"], 16), a.timeout,
                       progress=depth > 1000)
    dt = time.time() - t0
    if depth > 1000:
        print()
    if status.startswith("serial-error"):
        print(f"\nSERIAL LINK LOST after {dt:.1f}s — {status}")
        print("\n  The port disappeared mid-scan. This is not a mining failure:")
        print("  the board answered a ping moments earlier. In likelihood order:")
        print("   1. Windows suspended the idle USB device. Device Manager ->")
        print("      the FTDI port -> Power Management -> untick 'Allow the")
        print("      computer to turn off this device to save power'.")
        print("   2. A marginal cable or port. Try another of each — the same")
        print("      link already failed once during programming.")
        print("   3. Confirm it is duration-related by running a shorter scan:")
        print("        --depth 100000    (about a tenth of the time)")
        sys.exit(1)
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


def fetch_tip_context(refresh: bool, host: str, port: int):
    """Get the chain tip, median-time-past and nBits the candidate must satisfy.

    This shells out to live/fetch_tip_context.py rather than reimplementing the
    wire protocol. That script parses every value from raw block bytes received
    over the network, never from a node's self-reported summary, and it is the
    path that produced the four anchors already on the chain. A second
    implementation here would be a second thing to get wrong.
    """
    ctx_path = ROOT / "live" / "tip-context.json"
    if refresh:
        import subprocess
        print(f"fetching tip context from {host}:{port} ...")
        r = subprocess.run([sys.executable, str(ROOT / "live" / "fetch_tip_context.py"),
                            host, str(port)], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"tip fetch failed:\n{r.stdout}\n{r.stderr}")
    if not ctx_path.is_file():
        raise SystemExit(f"no {ctx_path}; run with --refresh to fetch it")
    ctx = json.loads(ctx_path.read_text())
    age = time.time() - time.mktime(time.strptime(ctx["acquired_utc"], "%Y-%m-%dT%H:%M:%SZ"))
    if not refresh and age > 3600:
        print(f"WARNING: tip context is {age/3600:.1f} hours old. A block mined on a "
              f"stale parent is worthless — use --refresh.")
    return ctx


def cmd_mine(a):
    """Mine a real block on top of the live chain tip.

    Deliberate properties, each of which is a decision rather than an accident:

    - **Nothing is broadcast unless --submit is given.** Submitting a block is
      irreversible and visible to everyone on the chain. Mining it is not. The
      two are separated so that a mistake in the first cannot become a mistake
      in the second.
    - **The FPGA never decides validity.** It reports nonces whose digest ends in
      a zero word; at difficulty 1 roughly one in 65,536 of those is still above
      the target. `scan()` re-checks every candidate against the exact compact
      target using the same code path that validates blocks from the network.
    - **Rounds are time-bounded, not exhaustion-bounded.** The RTL instantiates
      its cores with nonce_count = 0, meaning "run to the 2^32 wrap", so the
      'E' exhausted report never arrives. A round therefore ends on a clock, and
      the default is derived from the measured hash rate rather than guessed.
    """
    from ctp.bitcoin_jan09 import make_block, with_nonce, compact_size

    ser = open_port(a.port, a.baud)
    if not ping(ser):
        raise SystemExit("no link — run 'ping' and see fpga/README.md bring-up")

    ctx = fetch_tip_context(a.refresh, a.host, a.port_p2p)
    prev = ctx["tip_hash"]
    mtp = int(ctx["median_time_past"])
    bits = int(ctx["tip_nBits"], 16)
    height = int(ctx["candidate_height"])

    if a.payload_hex:
        payload = bytes.fromhex(a.payload_hex)
    else:
        rep = json.loads((ROOT / "reports" / "verification.json").read_text())
        payload = bytes.fromhex(rep["anchor"]["payload_hex"])
        print("payload: reusing reports/verification.json anchor "
              "(pass --payload-hex for a fresh one)")

    # A full 2^32 sweep at the measured rate, plus 5% so a round genuinely
    # covers the space rather than stopping just short of it.
    round_s = a.round_seconds or (2**32 / (a.rate_mhs * 1e6)) * 1.05
    target = target_from_bits(bits)

    print(f"\nmining height {height} on {prev[:24]}…")
    print(f"  bits {hex(bits)}  mtp {mtp}  rate {a.rate_mhs} MH/s")
    print(f"  {a.rounds} round(s) of {round_s:.0f}s, one nTime each")
    print(f"  submit: {'YES — will broadcast on success' if a.submit else 'no (mine only)'}\n")

    for rnd in range(a.rounds):
        ntime = max(int(time.time()), mtp + 1)
        if ntime <= mtp:
            raise SystemExit("nTime cannot exceed median-time-past; clock is wrong")
        tmpl = make_block(payload, prev, ntime, bits, nonce=0)
        header0 = tmpl["header"]

        print(f"round {rnd+1}/{a.rounds}  nTime {ntime}")
        t0 = time.time()
        got, status = scan(ser, header0, 0, bits, round_s, progress=True)
        dt = time.time() - t0

        if status.startswith("serial-error"):
            print(f"\n  LINK LOST after {dt:.0f}s — {status}")
            sys.exit(1)

        if got:
            nonce, h, _ = got
            raw = with_nonce(header0, nonce) + compact_size(1) + tmpl["tx"]
            # Decide validity here, from the bytes, not from the FPGA's word.
            if int(block_hash(raw[:80]), 16) > target:
                print(f"\n  candidate {nonce} above target — filter false positive, "
                      "continuing")
                ser.write(b"S")
                continue
            print(f"\n\n  *** BLOCK FOUND at height {height} ***")
            print(f"  nonce  {nonce}")
            print(f"  hash   {h}")
            print(f"  {dt:.1f}s, {len(raw)} bytes")

            out = ROOT / "live" / "mine" / f"fpga-block-{height}-{h[:16]}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({
                "height": height, "hash": h, "nonce": nonce, "nTime": ntime,
                "prev_hash": prev, "bits": hex(bits), "median_time_past": mtp,
                "payload_hex": payload.hex(), "txid": tmpl["txid"],
                "raw_block_hex": raw.hex(),
                "mined_by": "FPGA, Cmod A7-35T, 12 cores at 77.419 MHz",
                "found_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "note": "PoW re-verified against the exact compact target by the "
                        "host before this file was written; the FPGA only filters.",
            }, indent=2) + "\n")
            print(f"  saved  {out.relative_to(ROOT)}")

            if not a.submit:
                print("\n  NOT submitted. This block exists only on this machine.")
                print("  To broadcast it:")
                print(f"    python scripts/submit_block.py {out.relative_to(ROOT)}")
                return
            print(f"\n  submitting to {a.host}:{a.port_p2p} ...")
            from ctp.p2p_v01 import submit_block
            ev = submit_block(a.host, a.port_p2p, raw)
            print(json.dumps(ev, indent=2) if ev else "  (no events returned)")
            print("\n  A successful send is NOT proof of acceptance. Confirm the")
            print("  block is on the chain:  python live/fetch_full_chain.py")
            return

        print(f"\n  no block in {dt:.0f}s ({status}); rolling nTime")
        ser.write(b"S")                       # abort before the next round
        time.sleep(0.1)
        if a.refresh and rnd + 1 < a.rounds:
            ctx = fetch_tip_context(True, a.host, a.port_p2p)
            if ctx["tip_hash"] != prev:
                print(f"  TIP MOVED to {ctx['tip_hash'][:24]}… — someone else won "
                      f"height {height}. Rebasing.")
                prev = ctx["tip_hash"]
                mtp = int(ctx["median_time_past"])
                bits = int(ctx["tip_nBits"], 16)
                height = int(ctx["candidate_height"])
                target = target_from_bits(bits)

    print(f"\nno block found in {a.rounds} round(s). Nothing was submitted.")


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
        if name == "mine":
            s.add_argument("--host", default="bitcoin.bitcoin-lab.org")
            s.add_argument("--port-p2p", type=int, default=18026)
            s.add_argument("--refresh", action="store_true",
                           help="fetch the chain tip before mining, and re-check it "
                                "between rounds. Without this a stale parent is used, "
                                "and a block on a stale parent is worthless.")
            s.add_argument("--rounds", type=int, default=1,
                           help="how many nTime values to try")
            s.add_argument("--round-seconds", type=float, default=None,
                           help="seconds per round; default is one full 2^32 sweep "
                                "at --rate-mhs plus 5%%")
            s.add_argument("--rate-mhs", type=float, default=6.9854,
                           help="measured hash rate, used only to size a round")
            s.add_argument("--payload-hex",
                           help="coinbase payload; defaults to the anchor in "
                                "reports/verification.json")
            s.add_argument("--submit", action="store_true",
                           help="BROADCAST a found block to the network. Without "
                                "this the block is only written to disk. Submitting "
                                "is irreversible and visible to everyone.")
        s.set_defaults(func=fn)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
