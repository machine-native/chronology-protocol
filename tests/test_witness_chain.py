from ctp.simulate import make_simulated_unsigned
from ctp.model import SignedObservation,verify_witness_chains
from ctp.hashsuite import digest_pair
def fake(u): return SignedObservation(u,[])
G=digest_pair(b"TEST/GENESIS",b"g")
def test_chain_linkage_without_crypto():
    a=make_simulated_unsigned("w",100,2,G,0,None)
    b=make_simulated_unsigned("w",200,2,G,1,a.lineage_id())
    ok,latest=verify_witness_chains([fake(b),fake(a)])
    assert ok and latest[0].unsigned.sequence==1
    bad=make_simulated_unsigned("w",200,2,G,1,None)
    assert not verify_witness_chains([fake(a),fake(bad)])[0]
