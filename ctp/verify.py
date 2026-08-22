from __future__ import annotations
from .model import verify_signed_observation, verify_signed_checkpoint, verify_witness_chains
from .merkle import merkle_pair
from .interval import consensus
from .bitcoin_jan09 import anchor_payload, anchor_scriptsig, verify_project_genesis, block_hash, verify_candidate_structure

def verify_bundle(history, signed_checkpoint, bitcoin_candidate_raw=None, candidate_median_time_past=None, genesis=None):
    """Verify an evidence bundle.

    Returns (checks, verdict). A check is True, False, or the string "UNAVAILABLE"
    when this machine's toolchain cannot perform it. If any check is UNAVAILABLE
    the verdict is INDETERMINATE_TOOLCHAIN — never FAIL, because failing to check
    is not the same as checking and finding a failure.
    """
    from .pq import PQUnavailable
    checks={}
    checks["PROJECT_GENESIS_REPRODUCES"]=verify_project_genesis()
    if genesis is not None:
        gid=genesis.genesis_id()
        checks["PROTOCOL_GENESIS_BINDING"]=(
            all(o.unsigned.genesis_id==gid for o in history)
            and signed_checkpoint.unsigned.genesis_id==gid
        )
    else:
        checks["PROTOCOL_GENESIS_BINDING"]=False
    try:
        checks["ALL_OBSERVATION_PQ_SIGNATURES"]=all(verify_signed_observation(o) for o in history)
    except PQUnavailable:
        checks["ALL_OBSERVATION_PQ_SIGNATURES"]="UNAVAILABLE"

    chain_ok,latest=verify_witness_chains(history)
    checks["WITNESS_CHAINS"]=chain_ok
    cp=signed_checkpoint.unsigned

    unique_latest=len({o.unsigned.witness_id for o in latest})==len(latest)
    checks["UNIQUE_CHECKPOINT_WITNESSES"]=unique_latest

    recomputed_records=sorted((o.record_commitment() for o in latest),key=lambda p:(p.sha256,p.shake384))
    checks["CHECKPOINT_LATEST_OBSERVATION_SET"]=recomputed_records==cp.observation_records
    checks["MERKLE_ROOT"]=merkle_pair(recomputed_records)==cp.merkle_root if recomputed_records else False

    c=consensus([o.unsigned.interval for o in latest],cp.f) if latest else {"q":-1,"verdict":"BAD"}
    checks["CONSENSUS_RULE"]=c["q"]==cp.q and c["verdict"]==cp.verdict and c.get("interval")==cp.interval
    try:
        checks["CHECKPOINT_PQ_SIGNATURES"]=verify_signed_checkpoint(signed_checkpoint)
    except PQUnavailable:
        checks["CHECKPOINT_PQ_SIGNATURES"]="UNAVAILABLE"

    cr=signed_checkpoint.record_commitment()
    payload=anchor_payload(cp.epoch,cr.sha256,cr.shake384)
    checks["ANCHOR_PAYLOAD_96"]=len(payload)==96
    checks["JAN09_COINBASE_SCRIPTSIG_98"]=len(anchor_scriptsig(payload))==98

    pow_present=False
    if bitcoin_candidate_raw is not None:
        checks["BITCOIN_RAW_STRUCTURE"]=verify_candidate_structure(bitcoin_candidate_raw,payload,candidate_median_time_past)
        header=bitcoin_candidate_raw[:80]
        h=block_hash(header)
        bits=int.from_bytes(header[72:76],"little")
        from .bitcoin_jan09 import target_from_bits
        pow_present=int(h,16)<=target_from_bits(bits)
        checks["BITCOIN_POW"]=pow_present

    # "UNAVAILABLE" is neither pass nor fail: the check did not happen.
    if any(v == "UNAVAILABLE" for v in checks.values()):
        return checks, "INDETERMINATE_TOOLCHAIN"

    non_pow=all(v for k,v in checks.items() if k!="BITCOIN_POW")
    verdict="FAIL"
    if non_pow:
        verdict="PASS" if (bitcoin_candidate_raw is not None and pow_present) else "PASS_PRE_POW"
    return checks,verdict
