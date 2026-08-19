from pathlib import Path
import tempfile
from ctp.hashsuite import digest_pair
from ctp.renewal import UnsignedRenewal,sign_renewal,verify_renewal,DOM_RENEWAL
from ctp.pq import generate_keypair,ML_DSA_87,SLH_DSA_SHAKE_256S

def test_real_pq_renewal_roundtrip():
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
