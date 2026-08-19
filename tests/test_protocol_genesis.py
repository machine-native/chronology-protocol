from ctp.genesis import build_protocol_genesis
def test_genesis_binds_normative_bytes():
    a=build_protocol_genesis(b"spec",b"inv")
    b=build_protocol_genesis(b"spec!",b"inv")
    assert a.genesis_id()!=b.genesis_id()
    assert a.cesium_cycles_per_tau_second==9192631770
    assert a.picoseconds_per_tau_second==10**12
