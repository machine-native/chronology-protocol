from ctp.bitcoin_jan09 import *
def test_target_and_genesis_pow():
    target=target_from_bits(GENESIS_BITS)
    assert int(GENESIS_HASH,16)<=target
    assert scan_nonces(GENESIS_RAW[:80],GENESIS_NONCE,1)==(GENESIS_NONCE,GENESIS_HASH)
