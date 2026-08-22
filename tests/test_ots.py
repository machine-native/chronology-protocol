import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.ots import parse, parse_file, OTSError, MAGIC

PROOFS = sorted((ROOT / "vectors" / "valid").glob("*.ots"))

# Attestations confirmed against blockstream.info (a third party) on 2026-08-21/22.
KNOWN_ROOTS = {
    963190: "6fb556ef0dab354fe0e7ad5f2f1262f18490f1fed0c2a915c9c5abb3de346e3d",
    963207: "386b55af90bb5139e52c8b34500823b16f8eb053e1f04748a32004e3101567da",
    963431: "19f12f74695e5de964683351a08bdd0f9918ae87d780c11f44897975b0575dfd",
}


@pytest.mark.skipif(not PROOFS, reason="no .ots proofs present")
def test_every_proof_parses_and_matches_its_bundle():
    import hashlib
    for p in PROOFS:
        proof = parse_file(p)
        assert proof.file_hash_op == "sha256"
        assert len(proof.file_digest) == 32
        bundle = p.with_suffix("")
        if bundle.is_file():
            assert hashlib.sha256(bundle.read_bytes()).digest() == proof.file_digest, p.name


@pytest.mark.skipif(not PROOFS, reason="no .ots proofs present")
def test_bitcoin_attestations_are_present_and_well_formed():
    seen_heights = set()
    for p in PROOFS:
        proof = parse_file(p)
        assert proof.bitcoin, f"{p.name} carries no Bitcoin attestation"
        for height, root in proof.bitcoin:
            assert 500_000 < height < 5_000_000, height
            assert len(root) == 64 and int(root, 16) >= 0
            seen_heights.add(height)
            if height in KNOWN_ROOTS:
                # pins the parser against roots independently confirmed on a
                # public explorer — a parsing regression cannot pass this
                assert root == KNOWN_ROOTS[height], f"height {height}"
    assert seen_heights & set(KNOWN_ROOTS), "none of the confirmed heights appeared"


def test_rejects_garbage_rather_than_guessing():
    with pytest.raises(OTSError):
        parse(b"not a proof at all")
    with pytest.raises(OTSError):
        parse(MAGIC + b"\x01\x08" + b"\x00" * 4)      # truncated digest


@pytest.mark.skipif(not PROOFS, reason="no .ots proofs present")
def test_reader_needs_no_third_party_packages():
    """The whole point: a cold-storage reader must not need a package index.

    Runs the parser in a subprocess with third-party site-packages suppressed
    (-S), so an accidental dependency in the read path fails here rather than in
    someone's air-gapped 2126 archive.
    """
    code = (
        "import sys; sys.path.insert(0, r'%s');\n"
        "from ctp.ots import parse_file;\n"
        "p = parse_file(r'%s');\n"
        "assert p.bitcoin, 'no attestation';\n"
        "print('OK', p.bitcoin[0][0])\n" % (ROOT, PROOFS[0])
    )
    r = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, f"read path pulled in a third-party import:\n{r.stderr}"
    assert r.stdout.startswith("OK")


def test_unavailable_toolchain_is_never_reported_as_failure():
    """Regression: an old OpenSSL must yield INDETERMINATE_TOOLCHAIN, not FAIL.

    An outside verifier on OpenSSL 3.0 saw every bundle report verdict FAIL with
    the PQ signature checks false, because a toolchain that could not run the
    algorithm produced the same False as a forged signature. They could have
    reasonably concluded the evidence was bad. "Cannot check" and "checked and
    failed" must never collapse into the same answer.
    """
    import ctp.pq as pq
    from ctp.bundle import EvidenceBundle
    from ctp.verify import verify_bundle

    bundle_path = ROOT / "vectors" / "valid" / "evidence-bundle-live-anchored.cbor"
    if not bundle_path.is_file():
        pytest.skip("bundle not present")

    saved = dict(pq._ALG_CACHE)
    try:
        pq._ALG_CACHE[pq.ML_DSA_87] = False
        pq._ALG_CACHE[pq.SLH_DSA_SHAKE_256S] = False
        b = EvidenceBundle.from_bytes(bundle_path.read_bytes())
        checks, verdict = verify_bundle(b.history, b.checkpoint, b.candidate_block,
                                        b.candidate_median_time_past, b.genesis)
        assert verdict == "INDETERMINATE_TOOLCHAIN", verdict
        assert checks["ALL_OBSERVATION_PQ_SIGNATURES"] == "UNAVAILABLE"
        assert checks["CHECKPOINT_PQ_SIGNATURES"] == "UNAVAILABLE"
        assert verdict != "FAIL"
    finally:
        pq._ALG_CACHE.clear()
        pq._ALG_CACHE.update(saved)
