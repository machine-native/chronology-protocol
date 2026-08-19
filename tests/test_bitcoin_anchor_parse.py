from ctp.bitcoin_jan09 import *
def test_anchor_extract_and_structure():
    p=anchor_payload(9,b"\x11"*32,b"\x22"*48)
    b=make_block(p,GENESIS_HASH,GENESIS_TIME+1,GENESIS_BITS,0)
    e=extract_anchor_from_coinbase(b["tx"])
    assert e["payload"]==p and e["epoch"]==9
    assert verify_candidate_structure(b["raw"],p,GENESIS_TIME)
    bad=bytearray(b["raw"]); bad[-10]^=1
    assert not verify_candidate_structure(bytes(bad),p,GENESIS_TIME)

def test_median_time_past_context():
    p=anchor_payload(1,b"\x33"*32,b"\x44"*48)
    b=make_block(p,GENESIS_HASH,GENESIS_TIME+1,GENESIS_BITS,0)
    assert verify_candidate_structure(b["raw"],p,GENESIS_TIME)
    assert not verify_candidate_structure(b["raw"],p,GENESIS_TIME+1)
