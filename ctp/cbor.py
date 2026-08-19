"""Restricted deterministic CBOR encoder/decoder for Chronology Protocol v0.1.

No floats, tags, indefinite lengths or duplicate map keys.
"""
from __future__ import annotations
from typing import Any

class CBORError(ValueError):
    pass

def _head(major: int, n: int) -> bytes:
    if n < 0:
        raise CBORError("negative length")
    base = major << 5
    if n < 24:
        return bytes([base | n])
    if n <= 0xff:
        return bytes([base | 24, n])
    if n <= 0xffff:
        return bytes([base | 25]) + n.to_bytes(2, "big")
    if n <= 0xffffffff:
        return bytes([base | 26]) + n.to_bytes(4, "big")
    if n <= 0xffffffffffffffff:
        return bytes([base | 27]) + n.to_bytes(8, "big")
    raise CBORError("integer too large")

def dumps(x: Any) -> bytes:
    if x is None:
        return b"\xf6"
    if x is False:
        return b"\xf4"
    if x is True:
        return b"\xf5"
    if isinstance(x, int) and not isinstance(x, bool):
        if x >= 0:
            return _head(0, x)
        return _head(1, -1 - x)
    if isinstance(x, bytes):
        return _head(2, len(x)) + x
    if isinstance(x, str):
        b = x.encode("utf-8")
        return _head(3, len(b)) + b
    if isinstance(x, (list, tuple)):
        return _head(4, len(x)) + b"".join(dumps(v) for v in x)
    if isinstance(x, dict):
        encoded = []
        for k, v in x.items():
            ek = dumps(k)
            encoded.append((ek, dumps(v)))
        encoded.sort(key=lambda kv: (len(kv[0]), kv[0]))
        return _head(5, len(encoded)) + b"".join(k + v for k, v in encoded)
    if isinstance(x, float):
        raise CBORError("floating point is forbidden")
    raise CBORError(f"unsupported type: {type(x).__name__}")

def _read_uint(data: bytes, pos: int, ai: int):
    if ai < 24:
        return ai, pos
    sizes = {24: 1, 25: 2, 26: 4, 27: 8}
    if ai not in sizes:
        raise CBORError("indefinite/reserved additional information forbidden")
    n = sizes[ai]
    if pos + n > len(data):
        raise CBORError("truncated integer")
    val = int.from_bytes(data[pos:pos+n], "big")
    # enforce shortest encoding
    if (ai == 24 and val < 24) or (ai == 25 and val <= 0xff) or (ai == 26 and val <= 0xffff) or (ai == 27 and val <= 0xffffffff):
        raise CBORError("non-canonical integer/length encoding")
    return val, pos+n

def _loads_one(data: bytes, pos: int):
    if pos >= len(data):
        raise CBORError("truncated")
    ib = data[pos]
    pos += 1
    major, ai = ib >> 5, ib & 31
    if major in (0, 1):
        n, pos = _read_uint(data, pos, ai)
        return (n if major == 0 else -1-n), pos
    if major in (2, 3):
        n, pos = _read_uint(data, pos, ai)
        if pos+n > len(data):
            raise CBORError("truncated string")
        b = data[pos:pos+n]
        pos += n
        if major == 2:
            return b, pos
        try:
            return b.decode("utf-8"), pos
        except UnicodeDecodeError as e:
            raise CBORError("invalid utf-8") from e
    if major == 4:
        n, pos = _read_uint(data, pos, ai)
        out = []
        for _ in range(n):
            v, pos = _loads_one(data, pos)
            out.append(v)
        return out, pos
    if major == 5:
        n, pos = _read_uint(data, pos, ai)
        out = {}
        enc_keys = []
        for _ in range(n):
            k_start = pos
            k, pos = _loads_one(data, pos)
            ek = data[k_start:pos]
            if k in out:
                raise CBORError("duplicate map key")
            v, pos = _loads_one(data, pos)
            out[k] = v
            enc_keys.append(ek)
        if enc_keys != sorted(enc_keys, key=lambda b: (len(b), b)):
            raise CBORError("non-canonical map-key ordering")
        return out, pos
    if major == 7 and ai == 20:
        return False, pos
    if major == 7 and ai == 21:
        return True, pos
    if major == 7 and ai == 22:
        return None, pos
    raise CBORError("floats/tags/simple values outside true/false/null are forbidden")

def loads(data: bytes):
    obj, pos = _loads_one(data, 0)
    if pos != len(data):
        raise CBORError("trailing bytes")
    if dumps(obj) != data:
        raise CBORError("not deterministic canonical encoding")
    return obj
