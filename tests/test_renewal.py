from pathlib import Path
import tempfile
import pytest
from ctp.hashsuite import digest_pair
from ctp.renewal import UnsignedRenewal,sign_renewal,verify_renewal,DOM_RENEWAL
from ctp.pq import generate_keypair,ensure_available,PQUnavailable,ML_DSA_87,SLH_DSA_SHAKE_256S

def test_real_pq_renewal_roundtrip():
    # An outside reviewer noted that on OpenSSL 3.0-3.4 this test raised a raw
    # RuntimeError traceback while test_pq.py skipped cleanly via PQUnavailable,
    # for the identical cause. PQUnavailable is the designed signal for "toolchain
    # too old", so it is honoured here too — an old OpenSSL should read as SKIPPED,
    # never as a crash the reader has to diagnose.
    try:
        ensure_available()
    except PQUnavailable as e:
        pytest.skip(f"OpenSSL lacks the required PQ algorithms: {e}")
    prior=digest_pair(b"TEST/PRIOR",b"history")
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); pairs=[]
        for alg,slug in [(ML_DSA_87,"m"),(SLH_DSA_SHAKE_256S,"s")]:
            priv=td/(slug+".pem");pub=td/(slug+".pub.pem")
            generate_keypair(alg,priv,pub)
            pairs.append((alg,priv,pub))
        r=UnsignedRenewal(prior,[prior],"PQ-5-successor-demo",1)
        sr=sign_renewal(r,pairs)
        assert verify_renewal(sr)
        assert sr.record_commitment()!=prior
