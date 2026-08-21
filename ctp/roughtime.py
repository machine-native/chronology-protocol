"""Roughtime (IETF draft-11 wire) client and offline verifier — CHRN witness profile.

Upgrade over the NTP profile: the server returns an Ed25519-SIGNED response whose
Merkle tree covers the client nonce. With the nonce derived from the sandwich
challenge q, the signature binds the whole exchange below B0 cryptographically —
`auth_state` becomes SERVER_SIGNED_ED25519 instead of UNAUTHENTICATED.

Verification chain (confirmed against roughtime.cloudflare.com, 2026-08-21):
  leaf  = SHA-512(0x00 || nonce)[:32];  node = SHA-512(0x01 || L || R)[:32]
  SREP contains ROOT/MIDP(seconds)/RADI(seconds); SIG = Ed25519(DELE.PUBK,
  "RoughTime v1 response signature\\0" || SREP); CERT.SIG = Ed25519(long-term key,
  "RoughTime v1 delegation signature--\\0" || DELE); MIDP within [MINT, MAXT].

Ed25519 verification uses the same OpenSSL-CLI pattern as ctp/pq.py: no new
Python dependencies. Long-term keys ride in the evidence blob; the key->operator
mapping is repository metadata (a pinned ecosystem snapshot), stated, not proven.
"""
from __future__ import annotations
import base64, hashlib, socket, struct, subprocess, tempfile, time
from pathlib import Path

from . import cbor

PS = 1_000_000_000_000
DOM_RT_NONCE = b"CHRONOLOGY/SANDWICH-RT-NONCE/v1"
CTX_RESPONSE = b"RoughTime v1 response signature\x00"
CTX_DELEGATION = b"RoughTime v1 delegation signature--\x00"
VERSION_DRAFT11 = 0x8000000B
MAGIC = b"ROUGHTIM"


def _tag(s) -> int:
    b = s.encode() if isinstance(s, str) else s
    return struct.unpack("<I", b)[0]


T_VER, T_NONC, T_ZZZZ = _tag("VER\x00"), _tag("NONC"), _tag("ZZZZ")
T_SIG, T_PATH, T_SREP, T_CERT, T_INDX = _tag(b"SIG\x00"), _tag("PATH"), _tag("SREP"), _tag("CERT"), _tag("INDX")
T_ROOT, T_MIDP, T_RADI = _tag("ROOT"), _tag("MIDP"), _tag("RADI")
T_DELE, T_PUBK, T_MINT, T_MAXT = _tag("DELE"), _tag("PUBK"), _tag("MINT"), _tag("MAXT")


def encode_message(tags: dict) -> bytes:
    items = sorted(tags.items())
    n = len(items)
    out = struct.pack("<I", n)
    off, offs = 0, []
    for i, (t, v) in enumerate(items):
        if i > 0:
            offs.append(off)
        off += len(v)
    for o in offs:
        out += struct.pack("<I", o)
    for t, _ in items:
        out += struct.pack("<I", t)
    for _, v in items:
        out += v
    return out


def decode_message(b: bytes) -> dict:
    n = struct.unpack("<I", b[:4])[0]
    offs = [0] + [struct.unpack("<I", b[4 + 4 * i:8 + 4 * i])[0] for i in range(n - 1)]
    ts = 4 + 4 * (n - 1)
    tags = [struct.unpack("<I", b[ts + 4 * i:ts + 4 * i + 4])[0] for i in range(n)]
    vs = ts + 4 * n
    return {t: b[vs + offs[i]:(vs + offs[i + 1] if i + 1 < n else len(b))]
            for i, t in enumerate(tags)}


def rt_nonce(q: bytes, host: str, sequence: int) -> bytes:
    if len(q) != 32 or not (0 <= sequence <= 0xFF):
        raise ValueError("bad challenge/sequence")
    return hashlib.sha512(DOM_RT_NONCE + b"\x00" + q + host.encode() + bytes([sequence])).digest()[:32]


def build_request(nonce32: bytes) -> bytes:
    base = {T_VER: struct.pack("<I", VERSION_DRAFT11), T_NONC: nonce32, T_ZZZZ: b""}
    msg = encode_message(base)
    msg = encode_message({**base, T_ZZZZ: b"\x00" * (1024 - len(msg) - 12)})
    return MAGIC + struct.pack("<I", len(msg)) + msg


def roughtime_exchange(host: str, port: int, nonce32: bytes, timeout: float = 6.0) -> dict:
    ip = socket.gethostbyname(host)
    req = build_request(nonce32)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t1_utc_ns = time.time_ns()
    t1 = time.monotonic_ns()
    s.sendto(req, (ip, port))
    resp, _ = s.recvfrom(4096)
    t4 = time.monotonic_ns()
    s.close()
    return {"host": host, "ip": ip, "port": port, "request": req, "response": bytes(resp),
            "t1_utc_ns": t1_utc_ns, "t1_mono_ns": t1, "t4_mono_ns": t4}


def _ed25519_verify(pub32: bytes, msg: bytes, sig: bytes) -> bool:
    der = bytes.fromhex("302a300506032b6570032100") + pub32
    pem = ("-----BEGIN PUBLIC KEY-----\n"
           + base64.encodebytes(der).decode() + "-----END PUBLIC KEY-----\n")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "p.pem").write_text(pem)
        (td / "m").write_bytes(msg)
        (td / "s").write_bytes(sig)
        try:
            r = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin",
                                "-inkey", str(td / "p.pem"), "-rawin",
                                "-in", str(td / "m"), "-sigfile", str(td / "s")],
                               capture_output=True, check=False)
        except FileNotFoundError as e:
            raise RuntimeError("openssl executable not found") from e
        return r.returncode == 0


def verify_response(response: bytes, nonce32: bytes, longterm_pub32: bytes) -> dict:
    """Full offline verification. Returns {"midp_s", "radi_s"} or raises ValueError."""
    body = response
    if response[:8] == MAGIC:
        body = response[12:12 + struct.unpack("<I", response[8:12])[0]]
    m = decode_message(body)
    srep_raw, cert_raw = m[T_SREP], m[T_CERT]
    srep, cert = decode_message(srep_raw), decode_message(cert_raw)
    dele_raw = cert[T_DELE]
    dele = decode_message(dele_raw)

    # Merkle inclusion of our nonce
    h = hashlib.sha512(b"\x00" + nonce32).digest()[:32]
    idx = struct.unpack("<I", m[T_INDX])[0]
    path = m[T_PATH]
    for i in range(0, len(path), 32):
        sib = path[i:i + 32]
        h = hashlib.sha512(b"\x01" + (sib + h if idx & 1 else h + sib)).digest()[:32]
        idx >>= 1
    if h != srep[T_ROOT]:
        raise ValueError("merkle root mismatch")

    if not _ed25519_verify(dele[T_PUBK], CTX_RESPONSE + srep_raw, m[T_SIG]):
        raise ValueError("response signature invalid")
    if not _ed25519_verify(longterm_pub32, CTX_DELEGATION + dele_raw, cert[T_SIG]):
        raise ValueError("delegation signature invalid")

    midp = struct.unpack("<Q", srep[T_MIDP])[0]
    radi = struct.unpack("<I", srep[T_RADI])[0]
    mint = struct.unpack("<Q", dele[T_MINT])[0]
    maxt = struct.unpack("<Q", dele[T_MAXT])[0]
    if not (mint <= midp <= maxt):
        raise ValueError("midpoint outside delegation window")
    return {"midp_s": midp, "radi_s": radi}


def derive_rt_measurement(ex: dict, verified: dict) -> dict:
    """(claimed_ps, uncertainty_ps) from a verified exchange.

    MIDP has one-second granularity at current servers; uncertainty = RADI
    + 1 s quantization + rtt/2 + local margin. Coarser than NTP, but signed.
    """
    rtt_ps = (ex["t4_mono_ns"] - ex["t1_mono_ns"]) * 1000
    claimed_ps = verified["midp_s"] * PS + PS // 2
    uncertainty_ps = (verified["radi_s"] + 1) * PS + rtt_ps // 2 + 2 * (PS // 1000)
    return {"claimed_ps": claimed_ps, "uncertainty_ps": uncertainty_ps, "rtt_ps": rtt_ps,
            "midp_s": verified["midp_s"], "radi_s": verified["radi_s"]}


def rt_evidence_blob(seq: int, ex: dict, longterm_pub32: bytes,
                     q: bytes, b0_hash_hex: str, session_id: bytes) -> bytes:
    return cbor.dumps({
        1: "ROUGHTIME/v1", 2: ex["host"], 3: ex["ip"], 4: ex["request"], 5: ex["response"],
        6: ex["t1_mono_ns"], 7: ex["t4_mono_ns"], 8: ex["t1_utc_ns"], 9: seq,
        10: q, 11: bytes.fromhex(b0_hash_hex), 12: session_id,
        13: longterm_pub32, 14: ex["port"],
    })
