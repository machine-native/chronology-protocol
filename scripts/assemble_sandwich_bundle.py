#!/usr/bin/env python3
"""Assemble the reality-sandwich bundle after block C is on the live chain.

Downloads the full chain, locates B0 and C, extracts the connecting headers and
any burial headers, attaches the recomputed ERA expectation, writes
vectors/valid/reality-sandwich-bundle.cbor, and verifies it offline.
"""
from __future__ import annotations
import hashlib, json, socket, struct, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp import cbor
from ctp.model import SignedObservation, SignedCheckpoint
from ctp.genesis import build_protocol_genesis
from ctp.bitcoin_jan09 import dsha, block_hash, extract_anchor_from_coinbase, parse_single_tx_block
from ctp.sandwich import SandwichBundle, verify_sandwich, era_expectation, parse_frame_origin, PS

MAGIC = bytes.fromhex("f00ba726")
GENESIS = "00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a"
SEED = ("bitcoin.bitcoin-lab.org", 18026)


def _msg(c, p): return MAGIC + c.encode().ljust(12, b"\x00") + struct.pack("<I", len(p)) + p


def _varint(n): return bytes([n]) if n < 0xFD else b"\xfd" + struct.pack("<H", n)


def _read(sock):
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


def fetch_chain():
    s = socket.create_connection(SEED, timeout=30)
    s.sendall(_msg("version", struct.pack("<i", 209) + struct.pack("<Q", 1)
                   + struct.pack("<q", int(time.time()))
                   + struct.pack("<Q", 1) + b"\x00" * 10 + b"\xff\xff"
                   + socket.inet_aton("0.0.0.0") + struct.pack(">H", SEED[1])))
    inv = None
    while inv is None:
        cmd, body = _read(s)
        if cmd is None: raise SystemExit("closed before inv")
        if cmd == "version":
            s.sendall(_msg("verack", b""))
            s.sendall(_msg("getblocks", struct.pack("<i", 209) + _varint(1)
                           + bytes.fromhex(GENESIS)[::-1] + b"\x00" * 32))
        elif cmd == "inv":
            n = body[0] if body[0] < 0xFD else struct.unpack("<H", body[1:3])[0]
            off = 1 if body[0] < 0xFD else 3
            inv = [body[off + i * 36 + 4: off + i * 36 + 36] for i in range(n)
                   if struct.unpack("<I", body[off + i * 36: off + i * 36 + 4])[0] == 2]
    blocks = {}
    for i in range(0, len(inv), 50):
        batch = inv[i:i + 50]
        s.sendall(_msg("getdata", _varint(len(batch)) + b"".join(struct.pack("<I", 2) + h for h in batch)))
        got, deadline = 0, time.time() + 60
        while got < len(batch) and time.time() < deadline:
            cmd, body = _read(s)
            if cmd is None: raise SystemExit("closed mid-download")
            if cmd == "block":
                h = dsha(body[:80])
                if h in [bytes(x) for x in batch]:
                    blocks[h] = body
                    got += 1
    s.close()
    if len(blocks) != len(inv): raise SystemExit("incomplete chain download")
    return [blocks[bytes(h)] for h in inv]      # heights 1..tip


def main():
    work = ROOT / "live" / "sandwich-work"
    b0_info = json.loads((work / "b0.json").read_text())
    session_id = bytes.fromhex((work / "session.hex").read_text().strip())
    payload = bytes.fromhex((work / "payload.hex").read_text().strip())
    history = [SignedObservation.from_obj(o) for o in cbor.loads((work / "history.cbor").read_bytes())]
    checkpoint = SignedCheckpoint.from_obj(cbor.loads((work / "checkpoint.cbor").read_bytes()))
    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(), (ROOT / "INVARIANTS.md").read_bytes())
    blobs = [p.read_bytes() for p in sorted((work / "evidence").glob("blob*.cbor"))]

    chain = fetch_chain()
    hashes = [block_hash(b[:80]) for b in chain]      # heights 1..tip
    if b0_info["hash"] not in hashes:
        raise SystemExit("B0 not found on live chain")
    b0_idx = hashes.index(b0_info["hash"])
    if b0_idx + 1 != b0_info["height"]:
        raise SystemExit(f"B0 height mismatch: chain says {b0_idx+1}, recorded {b0_info['height']}")

    c_idx = None
    for i in range(b0_idx + 1, len(chain)):
        try:
            _, tx = parse_single_tx_block(chain[i])
            if extract_anchor_from_coinbase(tx)["payload"] == payload:
                c_idx = i
                break
        except Exception:
            continue
    if c_idx is None:
        raise SystemExit("block C (epoch-1 payload) not found on live chain")

    path_headers = [chain[i][:80] for i in range(b0_idx + 1, c_idx)]
    b1_headers = [chain[i][:80] for i in range(c_idx + 1, len(chain))]

    origin_s = parse_frame_origin(history[0].unsigned.reference_frame)
    cp = checkpoint.unsigned
    expectation = era_expectation(origin_s, (cp.interval.lower + cp.interval.upper) // 2)

    bundle = SandwichBundle(
        b0_raw=bytes.fromhex(b0_info["raw_hex"]), b0_height=b0_info["height"],
        session_id=session_id, evidence=blobs, history=history, checkpoint=checkpoint,
        block_c_raw=chain[c_idx], path_headers=path_headers, b1_headers=b1_headers,
        expectation=expectation, genesis=genesis)
    raw = bundle.canonical()
    dest = ROOT / "vectors" / "valid" / "reality-sandwich-bundle.cbor"
    dest.write_bytes(raw)

    checks, verdict, facts = verify_sandwich(SandwichBundle.from_bytes(raw))
    report = {
        "bundle": str(dest.relative_to(ROOT)), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "b0": {"hash": facts["b0_hash"], "height": facts["b0_height"]},
        "block_c": {"hash": facts["block_c_hash"], "height": c_idx + 1},
        "burial_depth": facts["burial_depth"], "challenge": facts["challenge"],
        "checks": checks, "verdict": verdict,
    }
    (ROOT / "reports" / "sandwich-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    sys.exit(0 if verdict.startswith("SANDWICH_PASS") else 1)


if __name__ == "__main__":
    main()
