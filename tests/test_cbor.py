import pytest
from ctp import cbor

def test_roundtrip_and_order():
    o={10:b"x",1:1,2:"a",3:[1,-2,True,None]}
    b=cbor.dumps(o)
    assert cbor.loads(b)==o
    assert cbor.dumps(cbor.loads(b))==b

def test_float_forbidden():
    with pytest.raises(Exception):
        cbor.dumps({"x":1.25})
