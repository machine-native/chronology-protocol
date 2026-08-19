import pytest
from ctp import cbor
def test_noncanonical_integer_rejected():
    with pytest.raises(Exception):
        cbor.loads(b"\x18\x01")
def test_float_rejected_decode():
    with pytest.raises(Exception):
        cbor.loads(b"\xfb"+b"\x00"*8)
