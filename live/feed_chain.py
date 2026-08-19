#!/usr/bin/env python3
"""Feed the downloaded chain to a local unmodified Jan09-derived client, in order.

Connects to 127.0.0.1:18026 over the v0.1 wire (20-byte header, no checksum),
handshakes, and pushes every raw block from live/chain-blocks.hex as an unsolicited
`block` message — the same path a 2009 peer relay takes. The client validates each
block itself (ProcessBlock/AcceptBlock in its debug.log); this script proves nothing
and claims nothing beyond transmission.
"""
from __future__ import annotations
import socket, struct, sys, time
from pathlib import Path

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 18026
MAGIC = bytes.fromhex("f00ba726")
HERE = Path(__file__).resolve().parent


def msg(c, p): return MAGIC + c.encode().ljust(12, b"\x00") + struct.pack("<I", len(p)) + p


def main():
    blocks = [bytes.fromhex(l) for l in (HERE / "chain-blocks.hex").read_text().split()]
    s = socket.create_connection((HOST, PORT), timeout=30)
    s.sendall(msg("version", struct.pack("<i", 209) + struct.pack("<Q", 1)
                  + struct.pack("<q", int(time.time()))
                  + struct.pack("<Q", 1) + b"\x00" * 10 + b"\xff\xff"
                  + socket.inet_aton("127.0.0.1") + struct.pack(">H", PORT)))
    s.settimeout(5)
    try:
        hdr = s.recv(20)
        print("peer replied:", hdr[4:16].rstrip(b"\x00").decode(errors="replace") if len(hdr) == 20 else "(short)")
    except socket.timeout:
        print("no version reply (client may still process); continuing")
    for i, raw in enumerate(blocks, start=1):
        s.sendall(msg("block", raw))
        if i % 40 == 0:
            print(f"sent {i}/{len(blocks)}")
            time.sleep(0.5)
    print(f"sent {len(blocks)}/{len(blocks)} blocks")
    time.sleep(3)
    s.close()


if __name__ == "__main__":
    sys.exit(main())
