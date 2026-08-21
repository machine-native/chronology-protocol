"""Reality-sandwich construction and offline verification (CHRN sandwich v1).

Causal claim shape:  B0  ≺  acquisition  ≺  C  [≺ B1 ...]

- B0 is an anchor-chain block whose hash seeds a freshness challenge
  q = H(DOM || hash(B0) || session-id). Per-exchange nonces derived from q are
  embedded inside each acquisition's wire request and echoed by the remote
  source, so the acquired evidence bytes could not have been produced before
  B0's hash existed (lower causal bound).
- C is an anchor block whose CHRN payload commits (checkpoint -> merkle ->
  observation records -> source-evidence digests) to those same evidence bytes,
  so the evidence existed before C's proof-of-work was found (upper causal bound).
- B1... are blocks extending C (burial).

The sandwich proves WHEN evidence was acquired, never that its content is true.
Normative description: docs/REALITY-SANDWICH.md.
"""
from __future__ import annotations
import hashlib, platform, socket, struct, sys, time
from dataclasses import dataclass, field
from typing import Optional

from . import cbor
from .hashsuite import DigestPair, digest_pair, DOM_EVIDENCE, DOM_STATE, DOM_WITNESS
from .model import (SourceObservation, UnsignedObservation, SignedObservation,
                    SignedCheckpoint, sign_observation)
from .interval import Interval
from .genesis import ProtocolGenesis
from .bitcoin_jan09 import (block_hash, target_from_bits, dsha, parse_single_tx_block,
                            extract_anchor_from_coinbase, anchor_payload)
from .verify import verify_bundle

DOM_SANDWICH_Q = b"CHRONOLOGY/SANDWICH-CHALLENGE/v1"
DOM_SANDWICH_NONCE = b"CHRONOLOGY/SANDWICH-NONCE/v1"
NTP_UNIX_DELTA = 2208988800          # seconds between 1900-01-01 and 1970-01-01
PS = 1_000_000_000_000
LOCAL_TIMESTAMP_MARGIN_PS = 2_000_000_000_000 // 1000   # 2 ms expressed in ps

# SPEC §3: interval endpoints are integer picoseconds relative to a DECLARED
# chronology genesis. The sandwich frame declares its origin (a Unix UTC second,
# normally 00:00:00Z of the acquisition day) inside the frame string itself, so
# same-day offsets stay far below the canonical-CBOR uint64 ceiling.
FRAME_PREFIX = "UTC-PS-ORIGIN-"


def frame_for_origin(origin_unix_s: int) -> str:
    return f"{FRAME_PREFIX}{origin_unix_s}/v1"


def parse_frame_origin(frame: str) -> int:
    if not frame.startswith(FRAME_PREFIX) or not frame.endswith("/v1"):
        raise ValueError(f"unknown reference frame: {frame}")
    return int(frame[len(FRAME_PREFIX):-3])


def challenge(b0_hash_hex: str, session_id: bytes) -> bytes:
    if len(session_id) != 32:
        raise ValueError("session_id must be 32 bytes")
    return hashlib.sha256(DOM_SANDWICH_Q + b"\x00" + bytes.fromhex(b0_hash_hex) + session_id).digest()


def exchange_nonce(q: bytes, host: str, sequence: int) -> bytes:
    if len(q) != 32:
        raise ValueError("challenge must be 32 bytes")
    if not (0 <= sequence <= 0xFF):
        raise ValueError("sequence out of range")
    return hashlib.sha256(DOM_SANDWICH_NONCE + b"\x00" + q + host.encode() + bytes([sequence])).digest()[:8]


def _ntp_ts_to_ps(raw8: bytes) -> int:
    secs = struct.unpack(">I", raw8[:4])[0] - NTP_UNIX_DELTA
    frac = struct.unpack(">I", raw8[4:8])[0]
    return secs * PS + (frac * PS) // (1 << 32)


def _ntp_short_to_ps(raw4: bytes) -> int:
    secs = struct.unpack(">H", raw4[:2])[0]
    frac = struct.unpack(">H", raw4[2:4])[0]
    return secs * PS + (frac * PS) // (1 << 16)


def ntp_exchange(host: str, nonce8: bytes, timeout: float = 5.0):
    """One real NTPv4 client exchange with the challenge nonce as transmit timestamp."""
    ip = socket.gethostbyname(host)
    req = bytearray(48)
    req[0] = 0x23                     # LI=0, VN=4, mode=3 (client)
    req[40:48] = nonce8
    req = bytes(req)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t1_utc_ns = time.time_ns()
    t1_mono_ns = time.monotonic_ns()
    s.sendto(req, (ip, 123))
    resp, _ = s.recvfrom(512)
    t4_mono_ns = time.monotonic_ns()
    s.close()
    if len(resp) < 48:
        raise ValueError("short NTP response")
    return {"host": host, "ip": ip, "request": req, "response": bytes(resp[:48]),
            "t1_utc_ns": t1_utc_ns, "t1_mono_ns": t1_mono_ns, "t4_mono_ns": t4_mono_ns}


def derive_measurement(ex: dict):
    """Deterministically derive (claimed_ps, uncertainty_ps) from a recorded exchange.

    claimed = server transmit time + path_delay/2, where path_delay is the
    round trip minus server processing time, measured on the local monotonic
    clock. Uncertainty = path_delay/2 + server root_dispersion + root_delay/2
    + a fixed local timestamping margin. No local wall-clock value enters the claim.
    """
    resp = ex["response"]
    mode = resp[0] & 0x07
    stratum = resp[1]
    root_delay_ps = _ntp_short_to_ps(resp[4:8])
    root_disp_ps = _ntp_short_to_ps(resp[8:12])
    t2_ps = _ntp_ts_to_ps(resp[32:40])
    t3_ps = _ntp_ts_to_ps(resp[40:48])
    rtt_ps = (ex["t4_mono_ns"] - ex["t1_mono_ns"]) * 1000
    server_ps = t3_ps - t2_ps
    path_ps = max(rtt_ps - server_ps, 0)
    claimed_ps = t3_ps + path_ps // 2
    uncertainty_ps = path_ps // 2 + root_disp_ps + root_delay_ps // 2 + LOCAL_TIMESTAMP_MARGIN_PS
    return {"mode": mode, "stratum": stratum, "claimed_ps": claimed_ps,
            "uncertainty_ps": uncertainty_ps, "rtt_ps": rtt_ps,
            "root_delay_ps": root_delay_ps, "root_dispersion_ps": root_disp_ps}


def evidence_blob(seq: int, ex: dict, q: bytes, b0_hash_hex: str, session_id: bytes) -> bytes:
    return cbor.dumps({
        1: "NTP/v4-UDP", 2: ex["host"], 3: ex["ip"], 4: ex["request"], 5: ex["response"],
        6: ex["t1_mono_ns"], 7: ex["t4_mono_ns"], 8: ex["t1_utc_ns"], 9: seq,
        10: q, 11: bytes.fromhex(b0_hash_hex), 12: session_id,
    })


def machine_state_digest() -> DigestPair:
    blob = cbor.dumps({1: platform.node(), 2: platform.platform(), 3: sys.version})
    return digest_pair(DOM_STATE, blob)


# ---- Roughtime witness profile — signed time evidence ------------------------
def rt_unsigned(seq: int, ex: dict, meas: dict, blob: bytes, genesis_id, previous,
                origin_unix_s: int) -> UnsignedObservation:
    wid = digest_pair(DOM_WITNESS, ("ROUGHTIME:" + ex["host"]).encode()).sha256
    ev = digest_pair(DOM_EVIDENCE, blob)
    rel = meas["claimed_ps"] - origin_unix_s * PS
    src = SourceObservation("ROUGHTIME/v1", rel, meas["uncertainty_ps"],
                            "SERVER_SIGNED_ED25519", ev)
    state = machine_state_digest()
    return UnsignedObservation(
        witness_id=wid, genesis_id=genesis_id, sequence=seq, previous=previous,
        monotonic_ps=ex["t1_mono_ns"] * 1000,
        interval=Interval(rel - meas["uncertainty_ps"], rel + meas["uncertainty_ps"]),
        reference_frame=frame_for_origin(origin_unix_s), sources=[src],
        hardware_state=state, firmware_state=state)


# ---- optical (camera) witness profile — sandwich v2 --------------------------
def camera_evidence_blob(photo_digests: dict, exif_times_utc_ns: dict, camera_model: str,
                         place: str, claimed_utc_ns: int, uncertainty_ns: int,
                         q: bytes, b0_hash_hex: str, session_id: bytes) -> bytes:
    """Evidence blob for a handheld photographic observation.

    photo_digests: {filename: sha256 bytes} for every original frame.
    exif_times_utc_ns: {filename: DateTimeOriginal as UTC nanoseconds} (self-asserted
    by the camera clock; the sandwich, not EXIF, carries the causal claim).
    The challenge is bound two ways: recorded here, and HANDWRITTEN inside the
    frames — the latter is human-verifiable content, not machine cryptography,
    and the verifier only re-checks the recorded binding.
    """
    # times carried in UTC nanoseconds: absolute picoseconds would exceed the
    # canonical-CBOR uint64 ceiling (SPEC ps values are frame-relative, not absolute)
    return cbor.dumps({
        1: "CAMERA-PHOTO/v1", 2: dict(sorted(photo_digests.items())),
        3: dict(sorted(exif_times_utc_ns.items())), 4: camera_model, 5: place,
        6: claimed_utc_ns, 7: uncertainty_ns,
        10: q, 11: bytes.fromhex(b0_hash_hex), 12: session_id,
    })


def camera_unsigned(blob: bytes, witness_name: str, genesis_id, origin_unix_s: int,
                    monotonic_ns: int) -> UnsignedObservation:
    o = cbor.loads(blob)
    wid = digest_pair(DOM_WITNESS, ("CAMERA:" + witness_name).encode()).sha256
    ev = digest_pair(DOM_EVIDENCE, blob)
    rel = o[6] * 1000 - origin_unix_s * PS
    src = SourceObservation("CAMERA-PHOTO/v1", rel, o[7] * 1000, "OPERATOR_ASSERTED", ev)
    state = machine_state_digest()
    return UnsignedObservation(
        witness_id=wid, genesis_id=genesis_id, sequence=0, previous=None,
        monotonic_ps=monotonic_ns * 1000,
        interval=Interval(rel - o[7] * 1000, rel + o[7] * 1000),
        reference_frame=frame_for_origin(origin_unix_s), sources=[src],
        hardware_state=state, firmware_state=state)


def ntp_unsigned(seq: int, ex: dict, meas: dict, blob: bytes, genesis_id, previous,
                 origin_unix_s: int) -> UnsignedObservation:
    wid = digest_pair(DOM_WITNESS, ("NTP:" + ex["host"]).encode()).sha256
    ev = digest_pair(DOM_EVIDENCE, blob)
    rel = meas["claimed_ps"] - origin_unix_s * PS
    src = SourceObservation("NTP/v4-UDP", rel, meas["uncertainty_ps"],
                            "UNAUTHENTICATED", ev)
    state = machine_state_digest()
    return UnsignedObservation(
        witness_id=wid, genesis_id=genesis_id, sequence=seq, previous=previous,
        monotonic_ps=ex["t1_mono_ns"] * 1000,
        interval=Interval(rel - meas["uncertainty_ps"], rel + meas["uncertainty_ps"]),
        reference_frame=frame_for_origin(origin_unix_s), sources=[src],
        hardware_state=state, firmware_state=state)


# ---- Earth Rotation Angle expectation (IAU 2000) -----------------------------
# ERA(turns) = frac(0.7790572732640 + 1.00273781191135448 * (JD_UT1 - 2451545.0))
# Computed here from the consensus UTC midpoint with |UT1-UTC| bounded by 0.9 s.
# This is a deterministic MODEL EXPECTATION, never physical evidence.
ERA_A_NANO = 779057273             # 0.7790572732640 turns in nano-turns (rounds 0.264 nano away)
ERA_B_SCALED = 100273781191135448  # 1.00273781191135448 * 1e17
DUT1_BOUND_PS = 900 * (PS // 1000)


def era_expectation(origin_unix_s: int, mid_rel_ps: int) -> dict:
    """ERA at (origin + mid_rel). Inputs kept split so every stored field fits
    canonical-CBOR uint64; the absolute picosecond instant only exists as an
    intermediate Python integer."""
    j2000_unix_ps = 946728000 * PS   # JD 2451545.0 expressed on the UTC/UT1 scale
    dt_ps = origin_unix_s * PS + mid_rel_ps - j2000_unix_ps
    # (A + B * days) mod 1 turn, exact integer arithmetic in nano-turns:
    # B*days [nano-turns] = ERA_B_SCALED * dt_ps / (86400 * PS * 1e8)
    den = 86400 * PS * 10**8
    total_nano = ERA_A_NANO + (ERA_B_SCALED * dt_ps) // den
    era_nano = total_nano % 1_000_000_000
    unc_nano = (ERA_B_SCALED * DUT1_BOUND_PS) // den + 1
    return {1: "ERA-IAU2000/v1", 2: origin_unix_s, 3: mid_rel_ps, 4: era_nano,
            5: unc_nano, 6: DUT1_BOUND_PS, 7: "EXPECTATION_NOT_EVIDENCE"}


# ---- bundle ------------------------------------------------------------------
@dataclass
class SandwichBundle:
    b0_raw: bytes
    b0_height: int
    session_id: bytes
    evidence: list[bytes]
    history: list[SignedObservation]
    checkpoint: SignedCheckpoint
    block_c_raw: bytes
    path_headers: list[bytes]        # raw 80-byte headers strictly between B0 and C
    b1_headers: list[bytes]          # raw 80-byte headers extending C, in order
    expectation: dict
    genesis: ProtocolGenesis
    version: int = 1
    photo_manifest: Optional[dict] = None     # v2: {filename: sha256 bytes}
    prediction_json: Optional[bytes] = None   # v2: UTF-8 JSON, model expectation, never evidence

    def as_obj(self):
        o = {1: self.version, 2: self.b0_raw, 3: self.b0_height, 4: self.session_id,
             5: list(self.evidence), 6: [x.as_obj() for x in self.history],
             7: self.checkpoint.as_obj(), 8: self.block_c_raw,
             9: list(self.path_headers), 10: list(self.b1_headers),
             11: self.expectation, 12: self.genesis.as_obj()}
        if self.version >= 2:
            o[13] = dict(sorted((self.photo_manifest or {}).items()))
            o[14] = self.prediction_json or b""
        return o

    def canonical(self):
        return cbor.dumps(self.as_obj())

    @classmethod
    def from_bytes(cls, raw: bytes):
        o = cbor.loads(raw)
        if o[1] not in (1, 2):
            raise ValueError("unsupported sandwich bundle version")
        return cls(o[2], o[3], o[4], list(o[5]),
                   [SignedObservation.from_obj(x) for x in o[6]],
                   SignedCheckpoint.from_obj(o[7]), o[8], list(o[9]), list(o[10]),
                   o[11], ProtocolGenesis.from_obj(o[12]), o[1],
                   o.get(13), o.get(14))


def _header_pow_ok(header: bytes) -> bool:
    bits = int.from_bytes(header[72:76], "little")
    return int(block_hash(header), 16) <= target_from_bits(bits)


def verify_sandwich(b: SandwichBundle):
    checks = {}
    b0_header = b.b0_raw[:80]
    b0_hash = block_hash(b0_header)
    checks["S_B0_POW"] = _header_pow_ok(b0_header)

    q = challenge(b0_hash, b.session_id)

    # evidence blobs, typed: NTP gets nonce-echo re-derivation; camera gets
    # manifest + challenge binding (its handwritten in-frame code is
    # human-verifiable content, deliberately outside machine checks)
    ev_index = {}
    ok_nonce, ok_bind, ok_camera, ok_meas = True, True, True, True
    ok_rt, saw_rt, saw_camera = True, False, False
    for blob in b.evidence:
        try:
            o = cbor.loads(blob)
            if o[10] != q or o[11] != bytes.fromhex(b0_hash) or o[12] != b.session_id:
                ok_bind = False
            typ = o[1]
            if typ == "NTP/v4-UDP":
                host, seq, req, resp = o[2], o[9], o[4], o[5]
                n = exchange_nonce(q, host, seq)
                if req[40:48] != n or resp[24:32] != n or (resp[0] & 0x07) != 4 or not (1 <= resp[1] <= 15):
                    ok_nonce = False
                ex = {"host": host, "ip": o[3], "request": req, "response": resp,
                      "t1_utc_ns": o[8], "t1_mono_ns": o[6], "t4_mono_ns": o[7]}
                meas = derive_measurement(ex)
                ev_index[digest_pair(DOM_EVIDENCE, blob)] = ("NTP/v4-UDP", seq, meas)
            elif typ == "CAMERA-PHOTO/v1":
                saw_camera = True
                if b.version < 2 or (b.photo_manifest or {}) != o[2] or not o[2]:
                    ok_camera = False
                ev_index[digest_pair(DOM_EVIDENCE, blob)] = (
                    "CAMERA-PHOTO/v1", 0,
                    {"claimed_ps": o[6] * 1000, "uncertainty_ps": o[7] * 1000})
            elif typ == "ROUGHTIME/v1":
                saw_rt = True
                from .roughtime import (rt_nonce, verify_response, derive_rt_measurement,
                                        decode_message, MAGIC, T_NONC)
                import struct as _struct
                host, seq = o[2], o[9]
                n = rt_nonce(q, host, seq)
                req = o[4]
                req_body = req[12:12 + _struct.unpack("<I", req[8:12])[0]] if req[:8] == MAGIC else req
                if decode_message(req_body).get(T_NONC) != n:
                    ok_rt = False
                    continue
                try:
                    verified = verify_response(o[5], n, o[13])
                except ValueError:
                    ok_rt = False
                    continue
                ex = {"host": host, "t1_mono_ns": o[6], "t4_mono_ns": o[7]}
                meas = derive_rt_measurement(ex, verified)
                ev_index[digest_pair(DOM_EVIDENCE, blob)] = ("ROUGHTIME/v1", seq, meas)
            else:
                ok_bind = False
        except Exception:
            ok_nonce = ok_bind = False
    checks["S_NONCE_ECHO"] = ok_nonce
    checks["S_CHALLENGE_BINDING"] = ok_bind
    if saw_camera or (b.version >= 2 and b.photo_manifest):
        checks["S_CAMERA_BINDING"] = ok_camera and saw_camera
    if saw_rt:
        checks["S_ROUGHTIME_SIGNATURES"] = ok_rt

    # every observation's source evidence must resolve to a blob whose
    # deterministically re-derived measurement matches the signed claim,
    # expressed in one shared declared-origin frame
    matched = 0
    origin_s = None
    try:
        frames = {so.unsigned.reference_frame for so in b.history}
        if len(frames) == 1:
            origin_s = parse_frame_origin(next(iter(frames)))
    except Exception:
        origin_s = None
    if origin_s is None:
        ok_meas = False
    for so in b.history:
        u = so.unsigned
        for src in u.sources:
            key = DigestPair(src.evidence.sha256, src.evidence.shake384)
            if key not in ev_index or origin_s is None:
                ok_meas = False
                continue
            typ, seq, meas = ev_index[key]
            rel = meas["claimed_ps"] - origin_s * PS
            if (typ != src.source_type or seq != u.sequence or src.claimed_ps != rel
                    or src.uncertainty_ps != meas["uncertainty_ps"]
                    or u.interval != Interval(rel - meas["uncertainty_ps"],
                                              rel + meas["uncertainty_ps"])):
                ok_meas = False
            matched += 1
    checks["S_EVIDENCE_MEASUREMENT"] = ok_meas and matched == len(b.evidence) == len(b.history)

    # core protocol checks (PQ signatures, chains, consensus, payload-in-C, C PoW)
    core, _ = verify_bundle(b.history, b.checkpoint, b.block_c_raw, None, b.genesis)
    checks.update(core)

    # linkage B0 -> ... -> C
    ok_link = True
    prev = b0_hash
    for h in b.path_headers:
        if h[4:36][::-1].hex() != prev or not _header_pow_ok(h):
            ok_link = False
            break
        prev = block_hash(h)
    c_header = b.block_c_raw[:80]
    if c_header[4:36][::-1].hex() != prev:
        ok_link = False
    checks["S_LINKAGE_B0_TO_C"] = ok_link

    # burial B1...
    ok_b1 = True
    prev = block_hash(c_header)
    for h in b.b1_headers:
        if h[4:36][::-1].hex() != prev or not _header_pow_ok(h):
            ok_b1 = False
            break
        prev = block_hash(h)
    burial = len(b.b1_headers) if ok_b1 else 0
    checks["S_B1_CHAIN_VALID"] = ok_b1

    # expectation is recomputed, never trusted (and never treated as evidence)
    cp = b.checkpoint.unsigned
    ok_exp = False
    if cp.interval is not None and origin_s is not None:
        mid_rel = (cp.interval.lower + cp.interval.upper) // 2
        ok_exp = era_expectation(origin_s, mid_rel) == b.expectation
    checks["S_EXPECTATION_RECOMPUTED"] = ok_exp

    all_ok = all(checks.values())
    if not all_ok:
        verdict = "FAIL"
    elif burial >= 1:
        verdict = "SANDWICH_PASS"
    else:
        verdict = "SANDWICH_PASS_UNBURIED"
    return checks, verdict, {"b0_hash": b0_hash, "b0_height": b.b0_height,
                             "block_c_hash": block_hash(c_header), "burial_depth": burial,
                             "challenge": q.hex()}
