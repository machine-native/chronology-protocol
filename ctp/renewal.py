from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from . import cbor
from .hashsuite import DigestPair,digest_pair
from .model import SignatureEnvelope
from .pq import sign,verify,public_pem_bytes,ML_DSA_87,SLH_DSA_SHAKE_256S

DOM_RENEWAL=b"CHRONOLOGY/RENEWAL/v1"
DOM_RENEWAL_SIGN=b"CHRONOLOGY/RENEWAL-SIGN/v1"
DOM_RENEWAL_RECORD=b"CHRONOLOGY/RENEWAL-RECORD/v1"

@dataclass
class UnsignedRenewal:
    previous_lineage: DigestPair
    prior_evidence: list[DigestPair]
    successor_profile: str
    sequence: int
    version:int=1
    def as_obj(self):
        return {1:self.version,2:self.previous_lineage.as_obj(),3:[x.as_obj() for x in self.prior_evidence],
                4:self.successor_profile,5:self.sequence}
    @classmethod
    def from_obj(cls,o):
        return cls(DigestPair.from_obj(o[2]),[DigestPair.from_obj(x) for x in o[3]],o[4],o[5],o[1])
    def canonical(self): return cbor.dumps(self.as_obj())
    def lineage_id(self): return digest_pair(DOM_RENEWAL,self.canonical())

@dataclass
class SignedRenewal:
    unsigned:UnsignedRenewal
    signatures:list[SignatureEnvelope]
    def as_obj(self): return {1:self.unsigned.as_obj(),2:[x.as_obj() for x in self.signatures]}
    def canonical(self): return cbor.dumps(self.as_obj())
    def record_commitment(self): return digest_pair(DOM_RENEWAL_RECORD,self.canonical())

def sign_renewal(r,keypairs):
    msg=DOM_RENEWAL_SIGN+b"\x00"+r.canonical()
    return SignedRenewal(r,[SignatureEnvelope(a,public_pem_bytes(pub),sign(a,priv,msg)) for a,priv,pub in keypairs])

def verify_renewal(s):
    import tempfile
    msg=DOM_RENEWAL_SIGN+b"\x00"+s.unsigned.canonical()
    req={ML_DSA_87,SLH_DSA_SHAKE_256S}; seen=set()
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        for i,e in enumerate(s.signatures):
            p=td/f"k{i}.pem";p.write_bytes(e.public_key_pem)
            if e.algorithm in seen or not verify(e.algorithm,p,msg,e.signature): return False
            seen.add(e.algorithm)
    return req.issubset(seen)
