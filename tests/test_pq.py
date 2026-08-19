from pathlib import Path
import tempfile
from ctp.pq import *
def test_pq_roundtrip():
    ensure_available()
    msg=b"chronology-pq-test"
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        for alg in (ML_DSA_87,SLH_DSA_SHAKE_256S):
            priv=td/(alg+".pem"); pub=td/(alg+".pub.pem")
            generate_keypair(alg,priv,pub)
            s=sign(alg,priv,msg)
            assert verify(alg,pub,msg,s)
            assert not verify(alg,pub,msg+b"x",s)
