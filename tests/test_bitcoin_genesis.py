from ctp.bitcoin_jan09 import *

def test_known_project_genesis():
    assert len(GENESIS_RAW)==270
    assert verify_project_genesis()
    assert block_hash(GENESIS_RAW[:80])==GENESIS_HASH
