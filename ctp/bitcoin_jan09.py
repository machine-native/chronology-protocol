"""January-2009-compatible Bitcoin serialization and CHRN anchor adapter."""
from __future__ import annotations
import hashlib, struct

COIN = 100_000_000
GENESIS_HASH = "00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a"
GENESIS_MERKLE = "aaa5bdfd6c4075a646db9975aab8515781c67fdd73b02df1773a4e1e21a38085"
GENESIS_TIME = 1785781375
GENESIS_NONCE = 33394338
GENESIS_BITS = 0x1D00FFFF
GENESIS_PUBKEY = bytes.fromhex(
"04c0414cfdcc009830708543b06e43a03570dc1ffa45ddf98657045e594a815eba7"
"94ca0602e8527d7ba3197e53c0c2f226892212aa99b827e8e2fd95fcea2f834")
GENESIS_RAW = bytes.fromhex(
"01000000"
"0000000000000000000000000000000000000000000000000000000000000000"
"8580a3211e4e3a77f12db073dd7fc6815751b8aa7599db46a675406cfdbda5aa"
"7fdc706a"
"ffff001d"
"a28efd01"
"01"
"01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff"
"3e04ffff001d0104365468652054696d65732030332f4175672f3230323620546f6c6c206f66207363"
"686f6f6c696e6720277374726169746a61636b657427ffffffff0100f2052a010000004341"
"04c0414cfdcc009830708543b06e43a03570dc1ffa45ddf98657045e594a815eba794ca0602e8527d7b"
"a3197e53c0c2f226892212aa99b827e8e2fd95fcea2f834ac00000000")

def dsha(b:bytes)->bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()

def compact_size(n:int)->bytes:
    if n<0: raise ValueError("negative")
    if n<253: return bytes([n])
    if n<=0xffff: return b"\xfd"+struct.pack("<H",n)
    if n<=0xffffffff: return b"\xfe"+struct.pack("<I",n)
    return b"\xff"+struct.pack("<Q",n)

def target_from_bits(bits:int)->int:
    exponent=bits>>24
    mantissa=bits & 0x007fffff
    return mantissa << (8*(exponent-3))

def block_hash(header:bytes)->str:
    if len(header)!=80: raise ValueError("header must be 80 bytes")
    return dsha(header)[::-1].hex()

def verify_project_genesis():
    if len(GENESIS_RAW) < 81:
        return False
    header = GENESIS_RAW[:80]
    try:
        n, pos = read_compact_size(GENESIS_RAW, 80)
    except NameError:
        # read_compact_size is defined later; runtime lookup succeeds after module load.
        return False
    if n != 1:
        return False
    tx = GENESIS_RAW[pos:]
    try:
        parse_coinbase_tx(tx)
    except Exception:
        return False
    return (
        len(GENESIS_RAW) == 270
        and block_hash(header) == GENESIS_HASH
        and int(GENESIS_HASH,16) <= target_from_bits(GENESIS_BITS)
        and header[36:68][::-1].hex() == GENESIS_MERKLE
        and dsha(tx) == header[36:68]
    )

def anchor_payload(epoch:int, checkpoint_sha256:bytes, checkpoint_shake384:bytes, flags:int=0x0003)->bytes:
    if len(checkpoint_sha256)!=32 or len(checkpoint_shake384)!=48:
        raise ValueError("bad checkpoint digest lengths")
    if not (0<=epoch<=0xffffffffffffffff): raise ValueError("epoch out of range")
    if not (0<=flags<=0xffff): raise ValueError("flags out of range")
    out = b"CHRN"+bytes([1,1])+flags.to_bytes(2,"big")+epoch.to_bytes(8,"big")+checkpoint_sha256+checkpoint_shake384
    assert len(out)==96
    return out

def anchor_scriptsig(payload:bytes)->bytes:
    if len(payload)!=96: raise ValueError("v1 payload must be 96 bytes")
    s=b"\x4c\x60"+payload
    assert len(s)==98
    # Jan09 historical rule: 2 <= coinbase scriptSig <= 100
    return s

def p2pk_script(pubkey:bytes=GENESIS_PUBKEY)->bytes:
    if len(pubkey)!=65: raise ValueError("expected uncompressed 65-byte pubkey")
    return b"\x41"+pubkey+b"\xac"

def coinbase_tx(payload:bytes, *, value:int=50*COIN, pubkey:bytes=GENESIS_PUBKEY)->bytes:
    sig=anchor_scriptsig(payload)
    spk=p2pk_script(pubkey)
    return (
        struct.pack("<I",1)+
        compact_size(1)+
        b"\x00"*32+struct.pack("<I",0xffffffff)+
        compact_size(len(sig))+sig+
        struct.pack("<I",0xffffffff)+
        compact_size(1)+
        struct.pack("<q",value)+
        compact_size(len(spk))+spk+
        struct.pack("<I",0)
    )

def txid(tx:bytes)->str:
    return dsha(tx)[::-1].hex()

def make_header(prev_hash_hex:str, merkle_internal:bytes, ntime:int, bits:int, nonce:int=0)->bytes:
    if len(prev_hash_hex)!=64: raise ValueError("prev hash hex")
    if len(merkle_internal)!=32: raise ValueError("merkle")
    return (
        struct.pack("<I",1)+bytes.fromhex(prev_hash_hex)[::-1]+merkle_internal+
        struct.pack("<III",ntime,bits,nonce)
    )

def make_block(payload:bytes, prev_hash_hex:str, ntime:int, bits:int, nonce:int=0, value:int=50*COIN):
    tx=coinbase_tx(payload,value=value)
    merkle=dsha(tx)
    header=make_header(prev_hash_hex,merkle,ntime,bits,nonce)
    raw=header+compact_size(1)+tx
    return {"tx":tx,"txid":txid(tx),"merkle_internal":merkle,"header":header,"raw":raw,
            "hash":block_hash(header),"pow_valid":int(block_hash(header),16)<=target_from_bits(bits)}

def with_nonce(header:bytes, nonce:int)->bytes:
    if len(header)!=80: raise ValueError
    return header[:76]+struct.pack("<I",nonce)

def scan_nonces(header:bytes,start=0,count=1_000_000):
    bits=struct.unpack("<I",header[72:76])[0]
    target=target_from_bits(bits)
    end=min(0x100000000,start+count)
    for n in range(start,end):
        h=with_nonce(header,n)
        digest=dsha(h)
        # displayed integer is big-endian of reversed digest == little-endian digest
        if int.from_bytes(digest,"little")<=target:
            return n, block_hash(h)
    return None


def read_compact_size(data:bytes,pos:int):
    if pos>=len(data): raise ValueError("truncated compact size")
    x=data[pos]; pos+=1
    if x<253: return x,pos
    if x==253:
        if pos+2>len(data): raise ValueError("truncated")
        n=struct.unpack("<H",data[pos:pos+2])[0]; pos+=2
        if n<253: raise ValueError("non-canonical compact size")
        return n,pos
    if x==254:
        if pos+4>len(data): raise ValueError("truncated")
        n=struct.unpack("<I",data[pos:pos+4])[0]; pos+=4
        if n<=0xffff: raise ValueError("non-canonical compact size")
        return n,pos
    if pos+8>len(data): raise ValueError("truncated")
    n=struct.unpack("<Q",data[pos:pos+8])[0]; pos+=8
    if n<=0xffffffff: raise ValueError("non-canonical compact size")
    return n,pos

def parse_coinbase_tx(tx:bytes):
    pos=0
    if len(tx)<4: raise ValueError("truncated tx")
    version=struct.unpack("<I",tx[pos:pos+4])[0]; pos+=4
    nin,pos=read_compact_size(tx,pos)
    if nin!=1: raise ValueError("expected one coinbase input")
    prev=tx[pos:pos+32]; pos+=32
    index=struct.unpack("<I",tx[pos:pos+4])[0]; pos+=4
    slen,pos=read_compact_size(tx,pos)
    script_sig=tx[pos:pos+slen]; pos+=slen
    sequence=struct.unpack("<I",tx[pos:pos+4])[0]; pos+=4
    nout,pos=read_compact_size(tx,pos)
    outputs=[]
    for _ in range(nout):
        value=struct.unpack("<q",tx[pos:pos+8])[0];pos+=8
        plen,pos=read_compact_size(tx,pos)
        spk=tx[pos:pos+plen];pos+=plen
        outputs.append((value,spk))
    locktime=struct.unpack("<I",tx[pos:pos+4])[0];pos+=4
    if pos!=len(tx): raise ValueError("trailing tx bytes")
    return {"version":version,"prev":prev,"index":index,"script_sig":script_sig,"sequence":sequence,
            "outputs":outputs,"locktime":locktime}

def extract_anchor_from_coinbase(tx:bytes):
    p=parse_coinbase_tx(tx)
    if p["prev"]!=b"\x00"*32 or p["index"]!=0xffffffff:
        raise ValueError("not coinbase")
    s=p["script_sig"]
    if not (2<=len(s)<=100):
        raise ValueError("Jan09 coinbase scriptSig size violation")
    if len(s)!=98 or s[:2]!=b"\x4c\x60":
        raise ValueError("not CHRN v1 anchor scriptSig")
    payload=s[2:]
    if payload[:4]!=b"CHRN" or payload[4]!=1 or payload[5]!=1:
        raise ValueError("bad anchor header")
    return {
        "payload":payload,"flags":int.from_bytes(payload[6:8],"big"),
        "epoch":int.from_bytes(payload[8:16],"big"),
        "sha256":payload[16:48],"shake384":payload[48:96]
    }

def parse_single_tx_block(raw:bytes):
    if len(raw)<81: raise ValueError("truncated block")
    header=raw[:80]; pos=80
    n,pos=read_compact_size(raw,pos)
    if n!=1: raise ValueError("v0.1 anchor template expects exactly one tx")
    tx=raw[pos:]
    # Transaction parser guarantees full tx consumption for one-tx block.
    parse_coinbase_tx(tx)
    return header,tx

def verify_candidate_structure(raw:bytes, expected_payload:bytes, median_time_past:int|None=None):
    header,tx=parse_single_tx_block(raw)
    parsed=extract_anchor_from_coinbase(tx)
    if parsed["payload"]!=expected_payload: return False
    merkle=header[36:68]
    if merkle!=dsha(tx): return False
    if block_hash(header)!=dsha(header)[::-1].hex(): return False
    if median_time_past is not None:
        ntime=struct.unpack("<I",header[68:72])[0]
        if ntime<=median_time_past: return False
    return True
