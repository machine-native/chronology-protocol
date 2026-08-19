from __future__ import annotations
import hashlib
from dataclasses import dataclass

@dataclass(frozen=True)
class DigestPair:
    sha256: bytes
    shake384: bytes

    def __post_init__(self):
        if len(self.sha256) != 32 or len(self.shake384) != 48:
            raise ValueError("invalid digest-pair lengths")

    def as_obj(self):
        return {1: self.sha256, 2: self.shake384}

    @classmethod
    def from_obj(cls, o):
        return cls(o[1], o[2])

    def hex_obj(self):
        return {"sha256": self.sha256.hex(), "shake256_384": self.shake384.hex()}

def framed(domain: bytes, message: bytes) -> bytes:
    if not domain or b"\x00" in domain:
        raise ValueError("domain must be non-empty and contain no NUL")
    return domain + b"\x00" + message

def digest_pair(domain: bytes, message: bytes) -> DigestPair:
    m = framed(domain, message)
    return DigestPair(
        hashlib.sha256(m).digest(),
        hashlib.shake_256(m).digest(48),
    )

DOM_OBS = b"CHRONOLOGY/OBSERVATION/v1"
DOM_OBS_SIGN = b"CHRONOLOGY/OBSERVATION-SIGN/v1"
DOM_OBS_RECORD = b"CHRONOLOGY/OBSERVATION-RECORD/v1"
DOM_CHECKPOINT = b"CHRONOLOGY/CHECKPOINT/v1"
DOM_CHECKPOINT_SIGN = b"CHRONOLOGY/CHECKPOINT-SIGN/v1"
DOM_CHECKPOINT_RECORD = b"CHRONOLOGY/CHECKPOINT-RECORD/v1"
DOM_MERKLE_LEAF = b"CHRONOLOGY/MERKLE-LEAF/v1"
DOM_MERKLE_NODE = b"CHRONOLOGY/MERKLE-NODE/v1"
DOM_EVIDENCE = b"CHRONOLOGY/SOURCE-EVIDENCE/v1"
DOM_STATE = b"CHRONOLOGY/STATE/v1"
DOM_WITNESS = b"CHRONOLOGY/WITNESS/v1"
