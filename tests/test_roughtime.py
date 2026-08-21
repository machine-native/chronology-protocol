import base64
import hashlib
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.roughtime import (encode_message, decode_message, rt_nonce, verify_response,
                           derive_rt_measurement, build_request, MAGIC,
                           T_SIG, T_PATH, T_SREP, T_CERT, T_INDX, T_ROOT, T_MIDP, T_RADI,
                           T_DELE, T_PUBK, T_MINT, T_MAXT,
                           CTX_RESPONSE, CTX_DELEGATION)


def _openssl_ok():
    try:
        subprocess.run(["openssl", "version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _keypair(tmp: Path, name: str):
    priv = tmp / f"{name}.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(priv)],
                   capture_output=True, check=True)
    pub_pem = subprocess.run(["openssl", "pkey", "-in", str(priv), "-pubout"],
                             capture_output=True, check=True).stdout
    der = base64.b64decode(b"".join(l for l in pub_pem.splitlines()
                                    if not l.startswith(b"-----")))
    return priv, der[-32:]


def _sign(priv: Path, msg: bytes, tmp: Path) -> bytes:
    m, s = tmp / "m.bin", tmp / "s.bin"
    m.write_bytes(msg)
    subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(priv), "-rawin",
                    "-in", str(m), "-out", str(s)], capture_output=True, check=True)
    return s.read_bytes()


def synthetic_response(tmp: Path, nonce: bytes, midp_s: int, radi_s: int = 2,
                       mint: int = None, maxt: int = None):
    lt_priv, lt_pub = _keypair(tmp, "lt")
    dl_priv, dl_pub = _keypair(tmp, "dl")
    mint = midp_s - 1000 if mint is None else mint
    maxt = midp_s + 1000 if maxt is None else maxt
    dele = encode_message({T_PUBK: dl_pub, T_MINT: struct.pack("<Q", mint),
                           T_MAXT: struct.pack("<Q", maxt)})
    cert = encode_message({T_DELE: dele, T_SIG: _sign(lt_priv, CTX_DELEGATION + dele, tmp)})
    root = hashlib.sha512(b"\x00" + nonce).digest()[:32]
    srep = encode_message({T_ROOT: root, T_MIDP: struct.pack("<Q", midp_s),
                           T_RADI: struct.pack("<I", radi_s)})
    msg = encode_message({T_SIG: _sign(dl_priv, CTX_RESPONSE + srep, tmp),
                          T_PATH: b"", T_SREP: srep, T_CERT: cert,
                          T_INDX: struct.pack("<I", 0)})
    return MAGIC + struct.pack("<I", len(msg)) + msg, lt_pub


@pytest.mark.skipif(not _openssl_ok(), reason="openssl unavailable")
def test_roughtime_synthetic_verify_and_tamper(tmp_path):
    q = bytes(range(32))
    nonce = rt_nonce(q, "test.example", 0)
    resp, lt_pub = synthetic_response(tmp_path, nonce, 1_787_000_000)
    v = verify_response(resp, nonce, lt_pub)
    assert v["midp_s"] == 1_787_000_000 and v["radi_s"] == 2

    ex = {"host": "test.example", "t1_mono_ns": 0, "t4_mono_ns": 40_000_000}
    m = derive_rt_measurement(ex, v)
    assert m["claimed_ps"] == 1_787_000_000 * 10**12 + 5 * 10**11
    assert m["uncertainty_ps"] > 3 * 10**12          # radi+quantization dominate

    # wrong nonce -> merkle mismatch
    with pytest.raises(ValueError):
        verify_response(resp, rt_nonce(q, "test.example", 1), lt_pub)
    # wrong long-term key -> delegation fails
    _, other_pub = synthetic_response(tmp_path, nonce, 1_787_000_000)
    with pytest.raises(ValueError):
        verify_response(resp, nonce, other_pub)
    # midpoint outside delegation window
    resp2, lt2 = synthetic_response(tmp_path, nonce, 1_787_000_000,
                                    mint=1_787_000_500, maxt=1_787_000_900)
    with pytest.raises(ValueError):
        verify_response(resp2, nonce, lt2)
    # bit-flip in the signed midpoint area -> signature failure
    flipped = bytearray(resp)
    flipped[-40] ^= 0x01
    with pytest.raises(ValueError):
        verify_response(bytes(flipped), nonce, lt_pub)


def test_request_shape():
    n = rt_nonce(bytes(32), "test.example", 0)
    req = build_request(n)
    assert req[:8] == MAGIC and len(req) == 1024
    body = decode_message(req[12:12 + struct.unpack("<I", req[8:12])[0]])
    from ctp.roughtime import T_NONC
    assert body[T_NONC] == n and len(n) == 32
