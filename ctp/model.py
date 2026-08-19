from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from . import cbor
from .hashsuite import *
from .pq import sign, verify, public_pem_bytes, ML_DSA_87, SLH_DSA_SHAKE_256S
from .merkle import merkle_pair
from .interval import Interval, consensus

@dataclass
class SignatureEnvelope:
    algorithm: str
    public_key_pem: bytes
    signature: bytes
    def as_obj(self):
        return {1:self.algorithm, 2:self.public_key_pem, 3:self.signature}
    @classmethod
    def from_obj(cls,o):
        return cls(o[1],o[2],o[3])

def _pair_or_none(p):
    return None if p is None else p.as_obj()

@dataclass
class SourceObservation:
    source_type: str
    claimed_ps: int
    uncertainty_ps: int
    auth_state: str
    evidence: DigestPair
    def as_obj(self):
        return {1:self.source_type,2:self.claimed_ps,3:self.uncertainty_ps,4:self.auth_state,5:self.evidence.as_obj()}
    @classmethod
    def from_obj(cls,o):
        return cls(o[1],o[2],o[3],o[4],DigestPair.from_obj(o[5]))

@dataclass
class UnsignedObservation:
    witness_id: bytes
    genesis_id: DigestPair
    sequence: int
    previous: Optional[DigestPair]
    monotonic_ps: int
    interval: Interval
    reference_frame: str
    sources: list[SourceObservation]
    hardware_state: DigestPair
    firmware_state: DigestPair
    version: int = 1
    def as_obj(self):
        return {
            1:self.version,2:self.witness_id,3:self.sequence,4:_pair_or_none(self.previous),
            5:self.monotonic_ps,6:self.interval.lower,7:self.interval.upper,8:self.reference_frame,
            9:[s.as_obj() for s in self.sources],10:self.hardware_state.as_obj(),11:self.firmware_state.as_obj(),
            12:self.genesis_id.as_obj()
        }
    @classmethod
    def from_obj(cls,o):
        return cls(
            witness_id=o[2],genesis_id=DigestPair.from_obj(o[12]),sequence=o[3],
            previous=None if o[4] is None else DigestPair.from_obj(o[4]),
            monotonic_ps=o[5],interval=Interval(o[6],o[7]),reference_frame=o[8],
            sources=[SourceObservation.from_obj(x) for x in o[9]],
            hardware_state=DigestPair.from_obj(o[10]),firmware_state=DigestPair.from_obj(o[11]),version=o[1]
        )
    def canonical(self):
        if self.version != 1: raise ValueError("unsupported observation version")
        if len(self.witness_id)!=32: raise ValueError("witness_id must be 32 bytes")
        if self.sequence<0: raise ValueError("negative sequence")
        if self.interval.lower>self.interval.upper: raise ValueError("invalid interval")
        if not self.sources: raise ValueError("observation must preserve at least one source")
        return cbor.dumps(self.as_obj())
    def lineage_id(self):
        return digest_pair(DOM_OBS, self.canonical())

@dataclass
class SignedObservation:
    unsigned: UnsignedObservation
    signatures: list[SignatureEnvelope]
    def as_obj(self):
        return {1:self.unsigned.as_obj(),2:[s.as_obj() for s in self.signatures]}
    @classmethod
    def from_obj(cls,o):
        return cls(UnsignedObservation.from_obj(o[1]),[SignatureEnvelope.from_obj(x) for x in o[2]])
    def canonical(self):
        return cbor.dumps(self.as_obj())
    def record_commitment(self):
        return digest_pair(DOM_OBS_RECORD, self.canonical())

def sign_observation(obs: UnsignedObservation, keypairs):
    msg = DOM_OBS_SIGN+b"\x00"+obs.canonical()
    env=[]
    for alg,priv,pub in keypairs:
        env.append(SignatureEnvelope(alg, public_pem_bytes(pub), sign(alg, priv, msg)))
    return SignedObservation(obs, env)

def verify_signed_observation(s: SignedObservation):
    from tempfile import TemporaryDirectory
    msg=DOM_OBS_SIGN+b"\x00"+s.unsigned.canonical()
    required={ML_DSA_87,SLH_DSA_SHAKE_256S}
    found=set()
    with TemporaryDirectory() as td:
        td=Path(td)
        for idx,e in enumerate(s.signatures):
            if e.algorithm in found:
                return False
            p=td/f"pub{idx}.pem"; p.write_bytes(e.public_key_pem)
            if not verify(e.algorithm,p,msg,e.signature):
                return False
            found.add(e.algorithm)
    return required.issubset(found)

def verify_witness_chains(history: list[SignedObservation]):
    by={}
    for s in history:
        by.setdefault(s.unsigned.witness_id,[]).append(s)
    latest=[]
    for wid,records in by.items():
        records.sort(key=lambda s:s.unsigned.sequence)
        if records[0].unsigned.sequence != 0:
            return False,[]
        prev=None
        seen=set()
        for idx,s in enumerate(records):
            if s.unsigned.sequence in seen or s.unsigned.sequence != idx:
                return False,[]
            seen.add(s.unsigned.sequence)
            if idx==0:
                if s.unsigned.previous is not None:
                    return False,[]
            else:
                if s.unsigned.previous != prev:
                    return False,[]
            prev=s.unsigned.lineage_id()
        latest.append(records[-1])
    latest.sort(key=lambda s:s.unsigned.witness_id)
    return True,latest

@dataclass
class UnsignedCheckpoint:
    epoch: int
    genesis_id: DigestPair
    previous: Optional[DigestPair]
    observation_records: list[DigestPair]
    merkle_root: DigestPair
    witness_count: int
    f: int
    q: int
    verdict: str
    interval: Optional[Interval]
    policy: str = "QSUPPORT-2FPLUS1/v1"
    version: int = 1
    def as_obj(self):
        return {
            1:self.version,2:self.epoch,3:_pair_or_none(self.previous),
            4:[p.as_obj() for p in self.observation_records],5:self.merkle_root.as_obj(),
            6:self.witness_count,7:self.f,8:self.q,9:self.verdict,
            10:None if self.interval is None else [self.interval.lower,self.interval.upper],
            11:self.policy,12:self.genesis_id.as_obj()
        }
    @classmethod
    def from_obj(cls,o):
        return cls(
            epoch=o[2],genesis_id=DigestPair.from_obj(o[12]),
            previous=None if o[3] is None else DigestPair.from_obj(o[3]),
            observation_records=[DigestPair.from_obj(x) for x in o[4]],merkle_root=DigestPair.from_obj(o[5]),
            witness_count=o[6],f=o[7],q=o[8],verdict=o[9],
            interval=None if o[10] is None else Interval(o[10][0],o[10][1]),policy=o[11],version=o[1]
        )
    def canonical(self):
        if self.version!=1: raise ValueError("unsupported checkpoint version")
        if self.witness_count != len(self.observation_records):
            raise ValueError("witness_count != observation record count")
        return cbor.dumps(self.as_obj())
    def lineage_id(self):
        return digest_pair(DOM_CHECKPOINT,self.canonical())

@dataclass
class SignedCheckpoint:
    unsigned: UnsignedCheckpoint
    signatures: list[SignatureEnvelope]
    def as_obj(self):
        return {1:self.unsigned.as_obj(),2:[s.as_obj() for s in self.signatures]}
    @classmethod
    def from_obj(cls,o):
        return cls(UnsignedCheckpoint.from_obj(o[1]),[SignatureEnvelope.from_obj(x) for x in o[2]])
    def canonical(self):
        return cbor.dumps(self.as_obj())
    def record_commitment(self):
        return digest_pair(DOM_CHECKPOINT_RECORD,self.canonical())

def build_checkpoint(epoch, signed_observations, f=1, previous=None):
    # Exactly one latest record per logical witness is required.
    wids=[s.unsigned.witness_id for s in signed_observations]
    if len(set(wids)) != len(wids):
        raise ValueError("duplicate logical witness in checkpoint")
    gids={s.unsigned.genesis_id for s in signed_observations}
    if len(gids)!=1:
        raise ValueError("observations span multiple protocol genesis objects")
    genesis_id=next(iter(gids))
    records=sorted((s.record_commitment() for s in signed_observations), key=lambda p:(p.sha256,p.shake384))
    mr=merkle_pair(records)
    result=consensus([s.unsigned.interval for s in signed_observations],f)
    interval=result.get("interval")
    return UnsignedCheckpoint(
        epoch=epoch,genesis_id=genesis_id,previous=previous,observation_records=records,merkle_root=mr,
        witness_count=len(signed_observations),f=f,q=result["q"],verdict=result["verdict"],interval=interval
    )

def sign_checkpoint(cp: UnsignedCheckpoint,keypairs):
    msg=DOM_CHECKPOINT_SIGN+b"\x00"+cp.canonical()
    env=[]
    for alg,priv,pub in keypairs:
        env.append(SignatureEnvelope(alg,public_pem_bytes(pub),sign(alg,priv,msg)))
    return SignedCheckpoint(cp,env)

def verify_signed_checkpoint(s: SignedCheckpoint):
    from tempfile import TemporaryDirectory
    msg=DOM_CHECKPOINT_SIGN+b"\x00"+s.unsigned.canonical()
    required={ML_DSA_87,SLH_DSA_SHAKE_256S}; found=set()
    with TemporaryDirectory() as td:
        td=Path(td)
        for idx,e in enumerate(s.signatures):
            if e.algorithm in found:
                return False
            p=td/f"pub{idx}.pem"; p.write_bytes(e.public_key_pem)
            if not verify(e.algorithm,p,msg,e.signature): return False
            found.add(e.algorithm)
    return required.issubset(found)
