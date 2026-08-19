from __future__ import annotations
from dataclasses import dataclass
from . import cbor
from .model import SignedObservation,SignedCheckpoint
from .genesis import ProtocolGenesis
from .bitcoin_jan09 import verify_candidate_structure

@dataclass
class EvidenceBundle:
    genesis:ProtocolGenesis
    history:list[SignedObservation]
    checkpoint:SignedCheckpoint
    candidate_block:bytes
    candidate_median_time_past:int
    version:int=1
    def as_obj(self):
        return {1:self.version,2:[x.as_obj() for x in self.history],3:self.checkpoint.as_obj(),
                4:self.candidate_block,5:self.candidate_median_time_past,6:self.genesis.as_obj()}
    def canonical(self): return cbor.dumps(self.as_obj())
    @classmethod
    def from_bytes(cls,b):
        o=cbor.loads(b)
        if o[1]!=1: raise ValueError("unsupported bundle version")
        return cls(ProtocolGenesis.from_obj(o[6]),[SignedObservation.from_obj(x) for x in o[2]],
                   SignedCheckpoint.from_obj(o[3]),o[4],o[5],o[1])
