#!/usr/bin/env python3
"""Fetch the live laboratory-chain tip context needed by build_live_template.py.

Connects to the public seed over the historical v0.1 wire format (20-byte header:
magic || command[12] || payload-size, no checksum), asks for the full inventory from
the genesis locator, downloads the last 11 blocks, and derives:

  - tip hash and height
  - pindexPrev->GetMedianTimePast()  (median of the last 11 block nTimes, v0.1 rule)
  - next-work bits (tip nBits; candidate height is not a 2016-block retarget boundary)

Every value is parsed from raw block bytes received over the wire, never from a
node's own reporting. Output: live/tip-context.json plus the raw tail block bytes
in live/tail-blocks.hex for independent re-derivation.

Usage: python live/fetch_tip_context.py [HOST] [PORT]
"""
from __future__ import annotations
import hashlib, json, socket, struct, sys, time
from pathlib import Path

HOST = sys.argv[1] if len(sys.argv) > 1 else "bitcoin.bitcoin-lab.org"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 18026
MAGIC = bytes.fromhex("f00ba726")
GENESIS = "00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a"
OUT = Path(__file__).resolve().parent


def dsha(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def msg(command: str, payload: bytes) -> bytes:
    return MAGIC + command.encode().ljust(12, b"\x00") + struct.pack("<I", len(payload)) + payload


def caddress() -> bytes:
    return struct.pack("<Q", 1) + b"\x00" * 10 + b"\xff\xff" + socket.inet_aton("0.0.0.0") + struct.pack(">H", PORT)


def varint(n: int) -> bytes:
    if n < 0xFD:
        return struct.pack("<B", n)
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    return b"\xfe" + struct.pack("<I", n)


def read_message(sock):
    hdr = b""
    while len(hdr) < 20:
        chunk = sock.recv(20 - len(hdr))
        if not chunk:
            return None, None
        hdr += chunk
    if hdr[:4] != MAGIC:
        raise SystemExit(f"wrong magic from peer: {hdr[:4].hex()}")
    cmd = hdr[4:16].rstrip(b"\x00").decode(errors="replace")
    size = struct.unpack("<I", hdr[16:20])[0]
    body = b""
    while len(body) < size:
        chunk = sock.recv(min(65536, size - len(body)))
        if not chunk:
            break
        body += chunk
    return cmd, body


def main() -> int:
    acquired_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    s = socket.create_connection((HOST, PORT), timeout=30)
    s.sendall(msg("version", struct.pack("<i", 209) + struct.pack("<Q", 1)
                  + struct.pack("<q", int(time.time())) + caddress()))
    # An inv carries at most 500 entries. Asking once from the genesis locator
    # therefore worked only while the chain was shorter than that, and stopped
    # working the moment it passed height 500 -- which it did in August 2026.
    # The fix is to page: ask again from the last hash received, and keep going
    # until a short inv says the tip has been reached.
    #
    # Height is still derived by COUNTING the hashes rather than by asking any
    # node for a number. That is the property worth preserving here: every value
    # in the output comes from block bytes on the wire, never from a node's own
    # reporting, and paging must not quietly become a request for a height.
    def getblocks_from(h_internal: bytes) -> None:
        loc = struct.pack("<i", 209) + varint(1) + h_internal + b"\x00" * 32
        s.sendall(msg("getblocks", loc))

    # This peer does not cap an inv at 500 -- it answered a genesis locator with
    # 529 hashes, its entire inventory. So the end of the chain cannot be
    # detected by a short page. What ends it is SILENCE: ask again from the last
    # hash received, and a peer with nothing after it simply does not reply.
    #
    # Silence is therefore treated as the tip, but only once at least one page
    # has arrived. Silence before any page is a failure, not an empty chain, and
    # conflating the two would report height 0 for an unreachable node.
    inv_hashes: list[bytes] = []
    page_from = bytes.fromhex(GENESIS)[::-1]
    pages = 0
    started = time.time()
    handshaken = False
    s.settimeout(20)
    while time.time() - started < 180:
        try:
            cmd, body = read_message(s)
        except (TimeoutError, socket.timeout):
            if inv_hashes:
                break                              # asked for more, got nothing: tip
            raise SystemExit("peer sent no inv before timing out")
        if cmd is None:
            if inv_hashes:
                break
            raise SystemExit("peer closed before any inv")
        if cmd == "version":
            s.sendall(msg("verack", b""))
            getblocks_from(page_from)
            handshaken = True
        elif cmd == "inv":
            n = body[0] if body[0] < 0xFD else struct.unpack("<H", body[1:3])[0]
            off = 1 if body[0] < 0xFD else 3
            page = [body[off + i * 36 + 4: off + i * 36 + 36]
                    for i in range(n)
                    if struct.unpack("<I", body[off + i * 36: off + i * 36 + 4])[0] == 2]
            if not page:
                break
            inv_hashes.extend(page)
            pages += 1
            page_from = page[-1]
            getblocks_from(page_from)            # ask again; silence ends it
    if not handshaken:
        raise SystemExit("no version message from peer")
    if not inv_hashes:
        raise SystemExit("no inv within deadline")
    if pages > 1:
        print(f"inv paged {pages}x for {len(inv_hashes)} blocks", file=sys.stderr)
    height = len(inv_hashes)                       # inv covers heights 1..height
    tail = inv_hashes[-11:]                        # internal byte order
    want = {bytes(h): i for i, h in enumerate(tail)}

    gd = varint(len(tail)) + b"".join(struct.pack("<I", 2) + h for h in tail)
    s.sendall(msg("getdata", gd))
    blocks: dict[bytes, bytes] = {}
    deadline = time.time() + 60
    while time.time() < deadline and len(blocks) < len(tail):
        cmd, body = read_message(s)
        if cmd is None:
            break
        if cmd == "block":
            h = dsha(body[:80])
            if h in want:
                blocks[h] = body
    s.close()
    if len(blocks) < len(tail):
        raise SystemExit(f"got {len(blocks)}/{len(tail)} tail blocks")

    ordered = [blocks[bytes(h)] for h in tail]
    headers = []
    for raw in ordered:
        v, prev, merkle, ntime, nbits, nonce = struct.unpack("<i32s32sIII", raw[:80])
        headers.append({"hash": dsha(raw[:80])[::-1].hex(), "prev": prev[::-1].hex(),
                        "nTime": ntime, "nBits": nbits, "nNonce": nonce})
    for a, b in zip(headers, headers[1:]):
        if b["prev"] != a["hash"]:
            raise SystemExit(f"tail linkage break at {b['hash']}")

    tip = headers[-1]
    times = sorted(h["nTime"] for h in headers)
    mtp = times[len(times) // 2]
    candidate_height = height + 1
    if candidate_height % 2016 == 0:
        raise SystemExit("candidate height is a retarget boundary; full GetNextWorkRequired needed")

    ctx = {
        "source": f"{HOST}:{PORT}",
        "acquired_utc": acquired_utc,
        "wire": "v0.1 20-byte header, no checksum; values parsed from raw block bytes",
        "tip_hash": tip["hash"],
        "tip_height": height,
        "tip_nTime": tip["nTime"],
        "tip_nBits": hex(tip["nBits"]),
        "candidate_height": candidate_height,
        "median_time_past": mtp,
        "median_time_past_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtp)),
        "median_window_nTimes": [h["nTime"] for h in headers],
        "next_bits": hex(tip["nBits"]),
        "next_bits_rule": "candidate height not a 2016-block boundary; v0.1 GetNextWorkRequired returns pindexLast->nBits",
        "tail_hashes": [h["hash"] for h in headers],
    }
    (OUT / "tip-context.json").write_text(json.dumps(ctx, indent=2) + "\n")
    (OUT / "tail-blocks.hex").write_text("\n".join(raw.hex() for raw in ordered) + "\n")
    print(json.dumps(ctx, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
