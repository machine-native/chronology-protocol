"""OpenSSL 3.5+ PQ signature wrapper.

Uses standardized implementations exposed by OpenSSL; no custom cryptography.
"""
from __future__ import annotations
from pathlib import Path
import subprocess, tempfile, shutil, re

ML_DSA_87 = "ML-DSA-87"
SLH_DSA_SHAKE_256S = "SLH-DSA-SHAKE-256s"

class PQUnavailable(RuntimeError):
    pass

def _run(args, *, input_bytes=None):
    try:
        p = subprocess.run(args, input=input_bytes, capture_output=True, check=False)
    except FileNotFoundError as e:
        raise PQUnavailable("openssl executable not found") from e
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{p.stderr.decode(errors='replace')}")
    return p.stdout

def openssl_version():
    out = _run(["openssl", "version"]).decode().strip()
    return out

def ensure_available():
    out = _run(["openssl", "list", "-signature-algorithms"]).decode(errors="replace")
    missing = [a for a in (ML_DSA_87, SLH_DSA_SHAKE_256S) if a not in out]
    if missing:
        raise PQUnavailable("OpenSSL lacks: " + ", ".join(missing))
    return openssl_version()

def generate_keypair(algorithm: str, private_pem: Path, public_pem: Path):
    private_pem.parent.mkdir(parents=True, exist_ok=True)
    _run(["openssl", "genpkey", "-algorithm", algorithm, "-out", str(private_pem)])
    _run(["openssl", "pkey", "-in", str(private_pem), "-pubout", "-out", str(public_pem)])

def sign(algorithm: str, private_pem: Path, message: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        msg = p/"msg.bin"; sig = p/"sig.bin"
        msg.write_bytes(message)
        _run(["openssl", "pkeyutl", "-sign", "-inkey", str(private_pem), "-in", str(msg), "-out", str(sig)])
        return sig.read_bytes()

def verify(algorithm: str, public_pem: Path, message: bytes, signature: bytes) -> bool:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        msg = p/"msg.bin"; sig = p/"sig.bin"
        msg.write_bytes(message); sig.write_bytes(signature)
        proc = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(public_pem),
             "-in", str(msg), "-sigfile", str(sig)],
            capture_output=True, check=False
        )
        return proc.returncode == 0

def public_pem_bytes(public_pem: Path) -> bytes:
    return public_pem.read_bytes()
