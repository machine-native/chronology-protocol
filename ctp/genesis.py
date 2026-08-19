from __future__ import annotations
from dataclasses import dataclass
from . import cbor
from .hashsuite import DigestPair,digest_pair

DOM_GENESIS=b"CHRONOLOGY/PROTOCOL-GENESIS/v1"
DOM_DOC=b"CHRONOLOGY/NORMATIVE-DOCUMENT/v1"

@dataclass(frozen=True)
class ProtocolGenesis:
    protocol_name:str
    protocol_version:str
    cesium_cycles_per_tau_second:int
    picoseconds_per_tau_second:int
    spec_commitment:DigestPair
    invariants_commitment:DigestPair
    encoding_profile:str="DETERMINISTIC-CBOR-SUBSET/v1"
    crypto_profile:str="PQ-5-DUAL/v1"
    version:int=1

    def as_obj(self):
        return {
            1:self.version,2:self.protocol_name,3:self.protocol_version,
            4:self.cesium_cycles_per_tau_second,5:self.picoseconds_per_tau_second,
            6:self.spec_commitment.as_obj(),7:self.invariants_commitment.as_obj(),
            8:self.encoding_profile,9:self.crypto_profile
        }
    @classmethod
    def from_obj(cls,o):
        return cls(o[2],o[3],o[4],o[5],DigestPair.from_obj(o[6]),DigestPair.from_obj(o[7]),o[8],o[9],o[1])
    def canonical(self): return cbor.dumps(self.as_obj())
    def genesis_id(self): return digest_pair(DOM_GENESIS,self.canonical())

def build_protocol_genesis(spec_bytes:bytes,invariants_bytes:bytes):
    return ProtocolGenesis(
        protocol_name="Chronology Protocol",
        protocol_version="0.1.0",
        cesium_cycles_per_tau_second=9_192_631_770,
        picoseconds_per_tau_second=1_000_000_000_000,
        spec_commitment=digest_pair(DOM_DOC,b"SPEC.md\x00"+spec_bytes),
        invariants_commitment=digest_pair(DOM_DOC,b"INVARIANTS.md\x00"+invariants_bytes),
    )
