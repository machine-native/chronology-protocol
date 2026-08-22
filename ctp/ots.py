"""Dependency-free reader for OpenTimestamps detached proofs (.ots).

Why this exists: an independent verifier pointed out that `scripts/ots_info.py`
imported the `opentimestamps` package while the deposit claimed to need no
third-party Python. They were right, and for a cold-storage archive the flaw is
worse than cosmetic — a reader in 2126 should not need a package index to check a
Bitcoin attestation. So the read path is implemented here from the format itself.

Scope, deliberately narrow:
  - PARSING a proof (this module) must never need anything but the standard
    library, because it is on the verification path.
  - CREATING or UPGRADING a proof still uses the reference library, because those
    need the network and calendar servers anyway and are not cold-storage
    concerns.

Format (per the OpenTimestamps specification):

    magic (31 B) | version varuint | file-hash-op byte | file digest | timestamp

    timestamp := { 0xff <step> }* <step>
    step      := 0x00 <attestation> | <op-tag> <op-args> <timestamp>
    attestation := tag(8 B) varbytes(payload)
        pending  tag 83dfe30d2ef90c8e -> payload: varstr uri
        bitcoin  tag 05889 60d73d71901 -> payload: varuint block height

Only the operations these proofs actually use are implemented; anything else
raises rather than guessing, because a silently mis-parsed attestation would be
worse than no reader at all.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field

MAGIC = bytes.fromhex("004f70656e54696d657374616d7073000050726f6f6600bf89e2e884e89294")
PENDING_TAG = bytes.fromhex("83dfe30d2ef90c8e")
BITCOIN_TAG = bytes.fromhex("0588960d73d71901")
LITECOIN_TAG = bytes.fromhex("06869a0d73d71b45")
ETHEREUM_TAG = bytes.fromhex("30fe8087b5c7ead7")

OP_SHA1, OP_RIPEMD160, OP_SHA256, OP_KECCAK256 = 0x02, 0x03, 0x08, 0x67
OP_APPEND, OP_PREPEND, OP_REVERSE, OP_HEXLIFY = 0xF0, 0xF1, 0xF2, 0xF3


class OTSError(ValueError):
    pass


class _Reader:
    def __init__(self, data: bytes):
        self.d, self.i = data, 0

    def byte(self) -> int:
        if self.i >= len(self.d):
            raise OTSError("truncated proof")
        b = self.d[self.i]
        self.i += 1
        return b

    def take(self, n: int) -> bytes:
        if self.i + n > len(self.d):
            raise OTSError("truncated proof")
        b = self.d[self.i:self.i + n]
        self.i += n
        return b

    def varuint(self) -> int:
        val, shift = 0, 0
        while True:
            b = self.byte()
            val |= (b & 0x7F) << shift
            if not (b & 0x80):
                return val
            shift += 7

    def varbytes(self) -> bytes:
        return self.take(self.varuint())


@dataclass
class Attestation:
    kind: str                 # "bitcoin" | "pending" | "litecoin" | "ethereum" | "unknown"
    height: int | None = None
    uri: str | None = None
    message: bytes = b""      # the value committed at this point in the tree


@dataclass
class Proof:
    file_digest: bytes
    file_hash_op: str
    attestations: list = field(default_factory=list)

    @property
    def bitcoin(self):
        """[(height, required_merkle_root_hex), ...] — what to check against Bitcoin."""
        return sorted({(a.height, a.message[::-1].hex())
                       for a in self.attestations if a.kind == "bitcoin"})

    @property
    def pending(self):
        return sorted({a.uri for a in self.attestations if a.kind == "pending"})


def _apply(op: int, msg: bytes, arg: bytes) -> bytes:
    if op == OP_SHA256:
        return hashlib.sha256(msg).digest()
    if op == OP_SHA1:
        return hashlib.sha1(msg).digest()
    if op == OP_RIPEMD160:
        h = hashlib.new("ripemd160")
        h.update(msg)
        return h.digest()
    if op == OP_KECCAK256:
        raise OTSError("keccak256 not supported by this reader")
    if op == OP_APPEND:
        return msg + arg
    if op == OP_PREPEND:
        return arg + msg
    if op == OP_REVERSE:
        return msg[::-1]
    if op == OP_HEXLIFY:
        return msg.hex().encode()
    raise OTSError(f"unknown operation 0x{op:02x}")


def _attestation(r: _Reader, msg: bytes) -> Attestation:
    tag = r.take(8)
    payload = r.varbytes()
    p = _Reader(payload)
    if tag == BITCOIN_TAG:
        return Attestation("bitcoin", height=p.varuint(), message=msg)
    if tag == PENDING_TAG:
        return Attestation("pending", uri=p.varbytes().decode("utf-8", "replace"), message=msg)
    if tag == LITECOIN_TAG:
        return Attestation("litecoin", height=p.varuint(), message=msg)
    if tag == ETHEREUM_TAG:
        return Attestation("ethereum", height=p.varuint(), message=msg)
    return Attestation("unknown", message=msg)


def _timestamp(r: _Reader, msg: bytes, out: list, depth: int = 0) -> None:
    if depth > 256:
        raise OTSError("proof nested too deeply")
    tag = r.byte()
    while tag == 0xFF:                       # fork: another branch follows
        _step(r, msg, out, depth + 1)
        tag = r.byte()
    _step(r, msg, out, depth + 1, tag)


def _step(r: _Reader, msg: bytes, out: list, depth: int, tag: int | None = None) -> None:
    if tag is None:
        tag = r.byte()
    if tag == 0x00:
        out.append(_attestation(r, msg))
        return
    arg = r.varbytes() if tag in (OP_APPEND, OP_PREPEND) else b""
    _timestamp(r, _apply(tag, msg, arg), out, depth)


def parse(data: bytes) -> Proof:
    """Parse a detached .ots file. Raises OTSError on anything unexpected."""
    r = _Reader(data)
    if r.take(len(MAGIC)) != MAGIC:
        raise OTSError("not an OpenTimestamps detached proof")
    version = r.varuint()
    if version != 1:
        raise OTSError(f"unsupported proof version {version}")
    op = r.byte()
    names = {OP_SHA256: "sha256", OP_SHA1: "sha1", OP_RIPEMD160: "ripemd160"}
    if op not in names:
        raise OTSError(f"unsupported file hash operation 0x{op:02x}")
    length = {OP_SHA256: 32, OP_SHA1: 20, OP_RIPEMD160: 20}[op]
    digest = r.take(length)
    out: list = []
    _timestamp(r, digest, out)
    return Proof(file_digest=digest, file_hash_op=names[op], attestations=out)


def parse_file(path) -> Proof:
    with open(path, "rb") as f:
        return parse(f.read())
