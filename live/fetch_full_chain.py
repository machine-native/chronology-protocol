#!/usr/bin/env python3
"""Download every block of the laboratory chain from the public seed, raw, in order.

Writes live/chain-blocks.hex (one hex-encoded raw block per line, heights 1..tip)
after verifying: hash of each block matches the seed's advertised inventory entry,
and prev-hash linkage holds from the fixed genesis forward.
"""
from __future__ import annotations
import hashlib, socket, struct, sys, time
from pathlib import Path

HOST, PORT = "bitcoin.bitcoin-lab.org", 18026
MAGIC = bytes.fromhex("f00ba726")
GENESIS = "00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a"
OUT = Path(__file__).resolve().parent


def dsha(b): return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def msg(c, p): return MAGIC + c.encode().ljust(12, b"\x00") + struct.pack("<I", len(p)) + p


def varint(n):
    if n < 0xFD: return struct.pack("<B", n)
    if n <= 0xFFFF: return b"\xfd" + struct.pack("<H", n)
    return b"\xfe" + struct.pack("<I", n)


def read_message(sock):
    hdr = b""
    while len(hdr) < 20:
        c = sock.recv(20 - len(hdr))
        if not c: return None, None
        hdr += c
    cmd = hdr[4:16].rstrip(b"\x00").decode(errors="replace")
    size = struct.unpack("<I", hdr[16:20])[0]
    body = b""
    while len(body) < size:
        c = sock.recv(min(65536, size - len(body)))
        if not c: break
        body += c
    return cmd, body


def main():
    s = socket.create_connection((HOST, PORT), timeout=30)
    s.sendall(msg("version", struct.pack("<i", 209) + struct.pack("<Q", 1)
                  + struct.pack("<q", int(time.time()))
                  + struct.pack("<Q", 1) + b"\x00" * 10 + b"\xff\xff"
                  + socket.inet_aton("0.0.0.0") + struct.pack(">H", PORT)))
    inv = None
    while inv is None:
        cmd, body = read_message(s)
        if cmd is None: raise SystemExit("closed before inv")
        if cmd == "version":
            s.sendall(msg("verack", b""))
            s.sendall(msg("getblocks", struct.pack("<i", 209) + varint(1)
                          + bytes.fromhex(GENESIS)[::-1] + b"\x00" * 32))
        elif cmd == "inv":
            n = body[0] if body[0] < 0xFD else struct.unpack("<H", body[1:3])[0]
            off = 1 if body[0] < 0xFD else 3
            inv = [body[off + i * 36 + 4: off + i * 36 + 36] for i in range(n)
                   if struct.unpack("<I", body[off + i * 36: off + i * 36 + 4])[0] == 2]
    print(f"inventory: {len(inv)} blocks (heights 1..{len(inv)})")
    blocks = {}
    for i in range(0, len(inv), 50):
        batch = inv[i:i + 50]
        s.sendall(msg("getdata", varint(len(batch)) + b"".join(struct.pack("<I", 2) + h for h in batch)))
        got = 0
        deadline = time.time() + 60
        while got < len(batch) and time.time() < deadline:
            cmd, body = read_message(s)
            if cmd is None: raise SystemExit("closed mid-download")
            if cmd == "block":
                h = dsha(body[:80])
                if h in [bytes(x) for x in batch]:
                    blocks[h] = body
                    got += 1
        print(f"  fetched {len(blocks)}/{len(inv)}")
    s.close()
    if len(blocks) != len(inv):
        raise SystemExit("incomplete download")
    ordered = [blocks[bytes(h)] for h in inv]
    prev = GENESIS
    for raw in ordered:
        p = raw[4:36][::-1].hex()
        if p != prev:
            raise SystemExit(f"linkage break: expected prev {prev}, got {p}")
        prev = dsha(raw[:80])[::-1].hex()
    (OUT / "chain-blocks.hex").write_text("\n".join(r.hex() for r in ordered) + "\n")
    print(f"tip: {prev}")
    print(f"wrote {len(ordered)} blocks to live/chain-blocks.hex, linkage verified from genesis")


if __name__ == "__main__":
    sys.exit(main())
