#!/usr/bin/env python3
from __future__ import annotations
import json, sys, tempfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from ctp.pq import ensure_available,generate_keypair,ML_DSA_87,SLH_DSA_SHAKE_256S
from ctp.simulate import make_four_witness_history
from ctp.model import build_checkpoint,sign_checkpoint
from ctp.bitcoin_jan09 import anchor_payload,make_block,GENESIS_HASH,GENESIS_BITS,GENESIS_TIME
from ctp.verify import verify_bundle
from ctp.bundle import EvidenceBundle
from ctp.genesis import build_protocol_genesis

def keypairs(base:Path,name:str):
    d=base/name; d.mkdir(parents=True,exist_ok=True)
    out=[]
    for alg,slug in [(ML_DSA_87,"mldsa87"),(SLH_DSA_SHAKE_256S,"slh256s")]:
        priv=d/f"{slug}.pem"; pub=d/f"{slug}.pub.pem"
        generate_keypair(alg,priv,pub)
        out.append((alg,priv,pub))
    return out

def main():
    openssl=ensure_available()
    reports=ROOT/"reports"; vectors=ROOT/"vectors"/"valid"
    reports.mkdir(exist_ok=True); vectors.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        genesis=build_protocol_genesis((ROOT/"SPEC.md").read_bytes(),(ROOT/"INVARIANTS.md").read_bytes())
        gid=genesis.genesis_id()
        witness_keys={n:keypairs(td,n) for n in ("w1","w2","w3","w4")}
        history,latest=make_four_witness_history(witness_keys,gid)
        cp=build_checkpoint(0,latest,f=1)
        coordinator_keys=keypairs(td,"checkpoint")
        scp=sign_checkpoint(cp,coordinator_keys)
        commitment=scp.record_commitment()
        payload=anchor_payload(cp.epoch,commitment.sha256,commitment.shake384)

        candidate=make_block(payload,GENESIS_HASH,GENESIS_TIME+1,GENESIS_BITS,nonce=0)
        bundle=EvidenceBundle(genesis,history,scp,candidate["raw"],GENESIS_TIME)
        bundle_bytes=bundle.canonical()
        bundle_path=vectors/"evidence-bundle.cbor"
        bundle_path.write_bytes(bundle_bytes)

        checks,verdict=verify_bundle(history,scp,candidate["raw"],GENESIS_TIME,genesis)
        report={
            "protocol":"Chronology Protocol v0.1.0",
            "openssl":openssl,
            "evidence_class":"SIMULATED",
            "protocol_genesis_id":gid.hex_obj(),
            "bundle":{"path":"vectors/valid/evidence-bundle.cbor","bytes":len(bundle_bytes),
                      "sha256":hashlib.sha256(bundle_bytes).hexdigest()},
            "witness_history":{"records":len(history),"logical_witnesses":len(latest),"latest_sequence":1},
            "checkpoint":{
                "epoch":cp.epoch,"verdict":cp.verdict,"q":cp.q,"f":cp.f,
                "interval_ps":None if cp.interval is None else [cp.interval.lower,cp.interval.upper],
                "record_commitment":commitment.hex_obj(),
            },
            "anchor":{
                "payload_hex":payload.hex(),"payload_bytes":len(payload),"coinbase_scriptsig_bytes":98,
                "candidate_prev_hash":GENESIS_HASH,"candidate_median_time_past":GENESIS_TIME,
                "candidate_txid":candidate["txid"],"candidate_block_hash_nonce0":candidate["hash"],
                "difficulty_bits":hex(GENESIS_BITS),"pow_valid_nonce0":candidate["pow_valid"],
                "live_chain_status":"NOT_CLAIMED"
            },
            "checks":checks,"verdict":verdict,
            "remaining_external_gate":[
                "replace offline previous-block reference with current live tip",
                "mine real difficulty-1 proof of work",
                "submit exact block to running Jan09-derived network",
                "capture unmodified-node acceptance and chain inclusion evidence"
            ]
        }
        (reports/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
        (vectors/"anchor-payload.hex").write_text(payload.hex()+"\n")
        (vectors/"candidate-block-nonce0.hex").write_text(candidate["raw"].hex()+"\n")
        (vectors/"candidate-header-nonce0.hex").write_text(candidate["header"].hex()+"\n")
        print(json.dumps(report,indent=2))
        if verdict=="FAIL": raise SystemExit(1)

if __name__=="__main__": main()
