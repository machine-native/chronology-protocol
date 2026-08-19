from __future__ import annotations
from .hashsuite import digest_pair, DOM_EVIDENCE, DOM_STATE, DOM_WITNESS
from .model import UnsignedObservation, SourceObservation, sign_observation
from .interval import Interval
from . import cbor

def make_simulated_unsigned(name:str, claimed_ps:int, uncertainty_ps:int, genesis_id, sequence:int=0, previous=None):
    wid=digest_pair(DOM_WITNESS,name.encode()).sha256
    source_data=cbor.dumps({1:"SIMULATED",2:name,3:claimed_ps,4:uncertainty_ps,5:sequence})
    ev=digest_pair(DOM_EVIDENCE,source_data)
    state=digest_pair(DOM_STATE,("state:"+name).encode())
    src=SourceObservation("SIMULATED",claimed_ps,uncertainty_ps,"SIMULATED",ev)
    return UnsignedObservation(
        witness_id=wid,genesis_id=genesis_id,sequence=sequence,previous=previous,monotonic_ps=claimed_ps,
        interval=Interval(claimed_ps-uncertainty_ps,claimed_ps+uncertainty_ps),
        reference_frame="SIMULATED-TAU/v1",sources=[src],hardware_state=state,firmware_state=state)

def make_four_witness_history(keypairs_by_name, genesis_id, base_ps=1_000_000_000_000):
    offsets={"w1":0,"w2":2_000,"w3":-1_000,"w4":5_000_000_000}
    uncertainty=10_000
    history=[]; latest=[]
    for name,off in offsets.items():
        first_u=make_simulated_unsigned(name,base_ps-1_000_000,uncertainty,genesis_id,0,None)
        first=sign_observation(first_u,keypairs_by_name[name])
        second_u=make_simulated_unsigned(name,base_ps+off,uncertainty,genesis_id,1,first_u.lineage_id())
        second=sign_observation(second_u,keypairs_by_name[name])
        history.extend([first,second]); latest.append(second)
    return history,latest
