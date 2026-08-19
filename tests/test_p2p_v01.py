import struct
from ctp.p2p_v01 import *
def test_message_frame_no_checksum():
    m=build_message("block",b"abc")
    assert m[:4]==DEFAULT_MAGIC
    assert m[4:16].rstrip(b"\x00")==b"block"
    assert struct.unpack("<I",m[16:20])[0]==3
    assert m[20:]==b"abc"
    assert len(m)==23
def test_ipv4_mapped_address():
    a=encode_address("127.0.0.1",18026)
    assert len(a)==26
    assert a[8:20]==b"\x00"*10+b"\xff\xff"
    assert a[20:24]==b"\x7f\x00\x00\x01"
    assert a[24:26]==struct.pack(">H",18026)
def test_version_payload_v01_shape():
    p=version_payload("127.0.0.1",18026,timestamp=1)
    assert len(p)==46
    assert struct.unpack("<i",p[:4])[0]==DEFAULT_PROTOCOL_VERSION
