#!/usr/bin/env python3
"""Independently check that every seed serves the same chain.

For each seed: v0.1 handshake, `getblocks` from the genesis locator, then compare
the advertised inventory against every other seed. Agreement is decided from the
block hashes themselves, not from any node's self-reporting.

A disagreement is not automatically a fault: seeds legitimately differ by a block
or two while a new block propagates. The output distinguishes "behind/ahead by N"
from "forked at height H", because only the latter is a problem.

Usage:
  python live/check_seeds.py                       # the default seed
  python live/check_seeds.py seed2.example:18026 seed3.example:18026
"""
from __future__ import annotations
import socket, struct, sys, time

MAGIC = bytes.fromhex("f00ba726")
GENESIS = "00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a"
DEFAULT = ["bitcoin.bitcoin-lab.org:18026"]


def _msg(c, p):
    return MAGIC + c.encode().ljust(12, b"\x00") + struct.pack("<I", len(p)) + p


def _varint(n):
    return bytes([n]) if n < 0xFD else b"\xfd" + struct.pack("<H", n)


def _read(sock):
    hdr = b""
    while len(hdr) < 20:
        c = sock.recv(20 - len(hdr))
        if not c:
            return None, None
        hdr += c
    if hdr[:4] != MAGIC:
        return "BAD-MAGIC", hdr[:4]
    cmd = hdr[4:16].rstrip(b"\x00").decode(errors="replace")
    size = struct.unpack("<I", hdr[16:20])[0]
    body = b""
    while len(body) < size:
        c = sock.recv(min(65536, size - len(body)))
        if not c:
            break
        body += c
    return cmd, body


def inventory(host, port, timeout=20):
    """Return (list of block hashes from height 1, peer protocol version)."""
    ip = socket.gethostbyname(host)
    s = socket.create_connection((ip, port), timeout=timeout)
    s.settimeout(timeout)
    try:
        s.sendall(_msg("version", struct.pack("<i", 209) + struct.pack("<Q", 1)
                       + struct.pack("<q", int(time.time()))
                       + struct.pack("<Q", 1) + b"\x00" * 10 + b"\xff\xff"
                       + socket.inet_aton("0.0.0.0") + struct.pack(">H", port)))
        ver = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            cmd, body = _read(s)
            if cmd is None:
                raise RuntimeError("closed before inv")
            if cmd == "BAD-MAGIC":
                raise RuntimeError(f"wrong network magic {body.hex()}")
            if cmd == "version":
                ver = struct.unpack("<i", body[:4])[0]
                s.sendall(_msg("verack", b""))
                s.sendall(_msg("getblocks", struct.pack("<i", 209) + _varint(1)
                               + bytes.fromhex(GENESIS)[::-1] + b"\x00" * 32))
            elif cmd == "inv":
                n = body[0] if body[0] < 0xFD else struct.unpack("<H", body[1:3])[0]
                off = 1 if body[0] < 0xFD else 3
                return [body[off + i*36 + 4: off + i*36 + 36][::-1].hex()
                        for i in range(n)
                        if struct.unpack("<I", body[off + i*36: off + i*36 + 4])[0] == 2], ver
        raise RuntimeError("no inv within timeout")
    finally:
        s.close()


def main():
    targets = sys.argv[1:] or DEFAULT
    results = {}
    for t in targets:
        host, _, port = t.partition(":")
        port = int(port or 18026)
        try:
            inv, ver = inventory(host, port)
            results[t] = inv
            print(f"{t:<40} OK   height {len(inv):<6} tip {inv[-1][:24]}…  (proto {ver})")
        except Exception as e:
            results[t] = None
            print(f"{t:<40} FAIL {e}")

    live = {k: v for k, v in results.items() if v}
    if len(live) < 2:
        print("\n(only one reachable seed — nothing to cross-check)")
        return 0 if live else 1

    print()
    names = list(live)
    ok = True
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = live[names[i]], live[names[j]]
            common = min(len(a), len(b))
            fork = next((h + 1 for h in range(common) if a[h] != b[h]), None)
            if fork:
                print(f"FORK  {names[i]} vs {names[j]} diverge at height {fork}")
                ok = False
            else:
                d = len(a) - len(b)
                rel = "level" if d == 0 else (f"{names[i]} ahead by {d}" if d > 0
                                              else f"{names[j]} ahead by {-d}")
                print(f"AGREE {names[i]} vs {names[j]} — same chain, {rel}")
    print("\nall seeds agree" if ok else "\nDISAGREEMENT — investigate before trusting any tip")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
