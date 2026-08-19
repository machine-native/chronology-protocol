from __future__ import annotations
from .hashsuite import digest_pair, DOM_MERKLE_LEAF, DOM_MERKLE_NODE, DigestPair
from . import cbor

def merkle_pair(record_commitments):
    """Return independent SHA-256 and SHAKE256-384 Merkle roots."""
    if not record_commitments:
        raise ValueError("empty merkle set")
    leaves_a=[]; leaves_b=[]
    for p in record_commitments:
        enc = cbor.dumps(p.as_obj())
        d = digest_pair(DOM_MERKLE_LEAF, enc)
        leaves_a.append(d.sha256); leaves_b.append(d.shake384)
    def reduce(nodes, which):
        while len(nodes) > 1:
            if len(nodes) & 1:
                nodes = nodes + [nodes[-1]]
            nxt=[]
            for i in range(0,len(nodes),2):
                d = digest_pair(DOM_MERKLE_NODE, nodes[i]+nodes[i+1])
                nxt.append(d.sha256 if which=="a" else d.shake384)
            nodes=nxt
        return nodes[0]
    return DigestPair(reduce(leaves_a,"a"), reduce(leaves_b,"b"))
