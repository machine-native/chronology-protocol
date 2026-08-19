#!/usr/bin/env python3
"""Acquire real sandwiched evidence: B0 -> challenge -> NTP witnesses -> checkpoint.

1. Fetches the current live-chain tip B0 over the v0.1 wire (raw bytes).
2. Derives the freshness challenge q = H(hash(B0) || session-id).
3. Performs two rounds of real NTPv4 exchanges against independent operators,
   with the per-exchange nonce derived from q embedded in each request's
   transmit timestamp and echoed by each server (lower causal bound).
4. Builds chained observations, signs them (ML-DSA-87 + SLH-DSA-SHAKE-256s),
   builds the epoch-1 checkpoint chained to the sealed v0.1.0 checkpoint, and
   emits the 96-byte anchor payload for mining into block C.

State is written to live/sandwich-work/ for the mining and assembly steps.
"""
from __future__ import annotations
import hashlib, json, os, socket, struct, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp import cbor
from ctp.pq import ensure_available, generate_keypair, ML_DSA_87, SLH_DSA_SHAKE_256S
from ctp.genesis import build_protocol_genesis
from ctp.model import build_checkpoint, sign_checkpoint, sign_observation
from ctp.bundle import EvidenceBundle
from ctp.bitcoin_jan09 import anchor_payload, dsha
from ctp.sandwich import (challenge, exchange_nonce, ntp_exchange, derive_measurement,
                          evidence_blob, ntp_unsigned)

HOSTS = ["time.nist.gov", "ptbtime1.ptb.de", "time.google.com",
         "time.windows.com", "time.apple.com"]
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


def fetch_tip_block():
    s = socket.create_connection(SEED, timeout=30)
    s.sendall(_msg("version", struct.pack("<i", 209) + struct.pack("<Q", 1)
                   + struct.pack("<q", int(time.time()))
                   + struct.pack("<Q", 1) + b"\x00" * 10 + b"\xff\xff"
                   + socket.inet_aton("0.0.0.0") + struct.pack(">H", SEED[1])))
    inv = None
    while inv is None:
        cmd, body = _read(s)
        if cmd is None: raise SystemExit("seed closed before inv")
        if cmd == "version":
            s.sendall(_msg("verack", b""))
            s.sendall(_msg("getblocks", struct.pack("<i", 209) + _varint(1)
                           + bytes.fromhex(GENESIS)[::-1] + b"\x00" * 32))
        elif cmd == "inv":
            n = body[0] if body[0] < 0xFD else struct.unpack("<H", body[1:3])[0]
            off = 1 if body[0] < 0xFD else 3
            inv = [body[off + i * 36 + 4: off + i * 36 + 36] for i in range(n)
                   if struct.unpack("<I", body[off + i * 36: off + i * 36 + 4])[0] == 2]
    tip_internal = inv[-1]
    height = len(inv)
    s.sendall(_msg("getdata", _varint(1) + struct.pack("<I", 2) + tip_internal))
    raw = None
    deadline = time.time() + 30
    while raw is None and time.time() < deadline:
        cmd, body = _read(s)
        if cmd is None: break
        if cmd == "block" and dsha(body[:80]) == bytes(tip_internal):
            raw = body
    s.close()
    if raw is None: raise SystemExit("tip block not received")
    return raw, height


def keypairs(base: Path, name: str):
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for alg, slug in [(ML_DSA_87, "mldsa87"), (SLH_DSA_SHAKE_256S, "slh256s")]:
        priv, pub = d / f"{slug}.pem", d / f"{slug}.pub.pem"
        generate_keypair(alg, priv, pub)
        out.append((alg, priv, pub))
    return out


def main():
    openssl = ensure_available()
    work = ROOT / "live" / "sandwich-work"
    (work / "evidence").mkdir(parents=True, exist_ok=True)

    b0_raw, b0_height = fetch_tip_block()
    b0_hash = dsha(b0_raw[:80])[::-1].hex()
    session_id = os.urandom(32)
    q = challenge(b0_hash, session_id)
    acquired_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    origin_s = (int(time.time()) // 86400) * 86400   # 00:00:00Z of the acquisition day
    print(f"B0: {b0_hash} height {b0_height}")
    print(f"challenge q: {q.hex()}")

    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()

    exchanges = {}      # host -> {seq: (ex, meas, blob)}
    for seq in (0, 1):
        for host in HOSTS:
            if seq == 1 and host not in exchanges:
                continue
            nonce = exchange_nonce(q, host, seq)
            try:
                ex = ntp_exchange(host, nonce)
            except Exception as e:
                print(f"  {host} seq {seq}: FAILED ({e}) — witness dropped")
                exchanges.pop(host, None)
                continue
            if ex["response"][24:32] != nonce:
                print(f"  {host} seq {seq}: nonce not echoed — witness dropped")
                exchanges.pop(host, None)
                continue
            meas = derive_measurement(ex)
            blob = evidence_blob(seq, ex, q, b0_hash, session_id)
            exchanges.setdefault(host, {})[seq] = (ex, meas, blob)
            print(f"  {host} seq {seq}: stratum {meas['stratum']} rtt {meas['rtt_ps']/1e9:.1f}ms "
                  f"unc ±{meas['uncertainty_ps']/1e9:.1f}ms echo ok")
    complete = {h: r for h, r in exchanges.items() if 0 in r and 1 in r}
    if len(complete) < 4:
        raise SystemExit(f"only {len(complete)} complete witnesses; consensus needs N >= 3f+1 = 4 for f=1")

    history, latest, blobs = [], [], []
    wkeys = {h: keypairs(work / "keys", h.replace(".", "-")) for h in complete}
    for host in sorted(complete):
        (ex0, m0, blob0) = complete[host][0]
        (ex1, m1, blob1) = complete[host][1]
        u0 = ntp_unsigned(0, ex0, m0, blob0, gid, None, origin_s)
        s0 = sign_observation(u0, wkeys[host])
        u1 = ntp_unsigned(1, ex1, m1, blob1, gid, u0.lineage_id(), origin_s)
        s1 = sign_observation(u1, wkeys[host])
        history.extend([s0, s1])
        latest.append(s1)
        blobs.extend([blob0, blob1])

    sealed = EvidenceBundle.from_bytes((ROOT / "vectors" / "valid" / "evidence-bundle.cbor").read_bytes())
    previous = sealed.checkpoint.record_commitment()
    cp = build_checkpoint(1, latest, f=1, previous=previous)
    scp = sign_checkpoint(cp, keypairs(work / "keys", "checkpoint"))
    commitment = scp.record_commitment()
    payload = anchor_payload(cp.epoch, commitment.sha256, commitment.shake384)

    (work / "b0.json").write_text(json.dumps(
        {"hash": b0_hash, "height": b0_height, "raw_hex": b0_raw.hex(),
         "acquired_utc": acquired_utc, "openssl": openssl}, indent=2) + "\n")
    (work / "session.hex").write_text(session_id.hex() + "\n")
    for i, blob in enumerate(blobs):
        (work / "evidence" / f"blob{i:02d}.cbor").write_bytes(blob)
    (work / "history.cbor").write_bytes(cbor.dumps([s.as_obj() for s in history]))
    (work / "checkpoint.cbor").write_bytes(scp.canonical())
    (work / "payload.hex").write_text(payload.hex() + "\n")

    print(json.dumps({
        "witnesses": sorted(complete), "history_records": len(history),
        "consensus": {"verdict": cp.verdict, "q": cp.q, "f": cp.f,
                      "interval_ps": None if cp.interval is None else [cp.interval.lower, cp.interval.upper]},
        "checkpoint_epoch": cp.epoch,
        "previous_checkpoint": previous.hex_obj()["sha256"][:16] + "...",
        "payload_hex": payload.hex(),
    }, indent=2))


if __name__ == "__main__":
    main()
