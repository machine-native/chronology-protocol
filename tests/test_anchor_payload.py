from ctp.bitcoin_jan09 import *
def test_exact_fit():
    p=anchor_payload(7,b"\x11"*32,b"\x22"*48)
    assert len(p)==96
    s=anchor_scriptsig(p)
    assert len(s)==98
    assert s[:2]==b"\x4c\x60"
    tx=coinbase_tx(p)
    assert len(tx)>0
