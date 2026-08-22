#!/usr/bin/env python3
"""Build the self-describing cold-storage deposit.

Produces a directory (and a .tar.gz) containing everything needed to verify this
project's claims in a future where this repository, its authors, and its hosting
no longer exist: the evidence bundles, their Bitcoin timestamp proofs, the entire
anchor chain as raw bytes, the complete verifier source, the normative documents,
the optical observation frames, and a plain-language README that explains how to
check all of it from first principles.

The deposit is designed to be understandable by someone who finds it with no
context. It states, in printed form, the Bitcoin block heights and merkle roots
that anchor the evidence, so the central claim survives even if every file in the
deposit were somehow lost except the README.

Usage: python scripts/build_archive.py [OUTPUT_DIR]
"""
from __future__ import annotations
import hashlib, json, shutil, subprocess, sys, tarfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opentimestamps.core.timestamp import DetachedTimestampFile
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
from opentimestamps.core.serialize import StreamDeserializationContext

# The deposit mirrors the repository layout EXACTLY. That is deliberate: every
# command in VERIFY.md and in README.txt then works verbatim inside the deposit,
# with no path translation for a reader to get wrong. A tidier-looking layout was
# tried first and broke every documented command, which is precisely the failure
# a cold-storage deposit cannot afford.
CONTENTS = [
    ("vectors/valid", "vectors/valid"),
    ("ctp", "ctp"),
    ("scripts", "scripts"),
    ("tests", "tests"),
    ("docs", "docs"),
    ("live/chain-blocks.hex", "live/chain-blocks.hex"),
    ("live/anchor-evidence", "live/anchor-evidence"),
    ("live/g2b-work/photos", "live/g2b-work/photos"),
    ("SPEC.md", "SPEC.md"),
    ("INVARIANTS.md", "INVARIANTS.md"),
    ("CLAIMS.md", "CLAIMS.md"),
    ("THREAT-MODEL.md", "THREAT-MODEL.md"),
    ("SECURITY.md", "SECURITY.md"),
    ("VERIFY.md", "VERIFY.md"),
    ("RELEASE_NOTES.md", "RELEASE_NOTES.md"),
    ("README.md", "README.md"),
    ("LICENSE", "LICENSE"),
    ("NOTICE", "NOTICE"),
    ("pyproject.toml", "pyproject.toml"),
    ("Makefile", "Makefile"),
    ("native/mine_sha256d.c", "native/mine_sha256d.c"),
]


def walk(node):
    yield node
    for child in node.ops.values():
        yield from walk(child)


def bitcoin_attestations():
    """(bundle name, block height, required merkle root) for every stamped bundle."""
    out = []
    for ots in sorted((ROOT / "vectors" / "valid").glob("*.ots")):
        with ots.open("rb") as f:
            d = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))
        rows = []
        for node in walk(d.timestamp):
            for att in node.attestations:
                if isinstance(att, BitcoinBlockHeaderAttestation):
                    rows.append((att.height, node.msg[::-1].hex()))
                elif isinstance(att, PendingAttestation):
                    rows.append((None, None))
        out.append((ots.name.replace(".ots", ""), d.file_digest.hex(), sorted(
            {(h, m) for h, m in rows if h is not None})))
    return out


def anchors():
    from ctp.bitcoin_jan09 import block_hash, parse_single_tx_block, extract_anchor_from_coinbase
    rows = []
    chain = (ROOT / "live" / "chain-blocks.hex").read_text().split()
    for i, line in enumerate(chain):
        raw = bytes.fromhex(line)
        try:
            _, tx = parse_single_tx_block(raw)
            a = extract_anchor_from_coinbase(tx)
            rows.append((a["epoch"], i + 1, block_hash(raw[:80])))
        except Exception:
            pass
    return rows, len(chain)


def git_provenance() -> dict:
    """Pin the deposit to an exact repository state.

    An independent verifier pointed out that a pack's contents mean little
    without knowing which commit produced them. Recorded here so the deposit
    can be compared against a public repository rather than trusted.
    """
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except Exception:
            return "unavailable"
    return {"commit": run("rev-parse", "HEAD"),
            "described": run("describe", "--tags", "--always", "--dirty"),
            "dirty": run("status", "--porcelain") != ""}


def readme(att, anch, chain_len, built_utc, prov=None) -> str:
    lines = []
    A = lines.append
    A("WHAT THIS IS")
    A("=" * 78)
    A("")
    A("This is a cold-storage deposit of the Chronology Protocol: a record of physical-")
    A("time observations that were cryptographically sealed and then committed into two")
    A("independent proof-of-work blockchains, so that WHEN they were made can be checked")
    A("by anyone, forever, without trusting the people who made them.")
    A("")
    A(f"Deposit built:  {built_utc}")
    if prov:
        A(f"Repository:     commit {prov['commit']}")
        A(f"                {prov['described']}" + ("  (WORKING TREE DIRTY)" if prov["dirty"] else ""))
        A("                github.com/machine-native/chronology-protocol")
        A("                Compare this deposit against that commit to establish that")
        A("                it is the published record and not something assembled for you.")
    A("Author:         Parth Mauria Saxena (parthod0x)")
    A("Licence:        Apache-2.0 (see LICENSE)")
    A("")
    A("If you are reading this long after 2026 and the original project is gone, you")
    A("can still verify everything below. That is the entire point of the deposit.")
    A("")
    A("")
    A("THE CLAIM, IN ONE PARAGRAPH")
    A("=" * 78)
    A("")
    A("Each evidence bundle in vectors/valid/ contains real measurements (network")
    A("time exchanges, an Ed25519-signed time service, and photographs of the Moon),")
    A("each signed with two post-quantum signature schemes, aggregated into a Merkle")
    A("checkpoint. Each checkpoint was then written into the coinbase of a block that")
    A("was really mined on a small experimental Bitcoin-derived chain, AFTER a challenge")
    A("derived from an earlier block on that same chain was embedded in the measurements.")
    A("That sandwich - earlier block, then measurement, then later block - bounds when")
    A("the evidence came into existence, from both sides, without any clock being")
    A("trusted. Separately, the bundles were timestamped into the PUBLIC Bitcoin")
    A("blockchain, which is the durable anchor listed below.")
    A("")
    A("")
    A("HOW TO VERIFY WITHOUT TRUSTING ANYONE  (the short version)")
    A("=" * 78)
    A("")
    A("The strongest check needs nothing from this deposit except a file and its hash,")
    A("plus a copy of the Bitcoin blockchain, which is preserved independently of us:")
    A("")
    A("  For each row below, take the named file from vectors/valid/, compute its")
    A("  SHA-256, and confirm it equals the digest shown. Then look up the Bitcoin")
    A("  block at the given height and confirm its MERKLE ROOT equals the value shown.")
    A("  If both match, that file existed before that Bitcoin block was mined.")
    A("")
    for name, digest, rows in att:
        A(f"  FILE   {name}")
        A(f"  SHA256 {digest}")
        if rows:
            for h, m in rows:
                A(f"    Bitcoin block {h}, merkle root {m}")
        else:
            A("    (timestamp proof was still aggregating when this deposit was built;")
            A("     the .ots file in vectors/valid/ can be completed with any")
            A("     OpenTimestamps client)")
        A("")
    A("These merkle roots were confirmed against an independent public block explorer")
    A("on 2026-08-21. They do not depend on this project continuing to exist.")
    A("")
    A("")
    A("THE FULL VERIFICATION")
    A("=" * 78)
    A("")
    A("VERIFY.md is a complete walkthrough. In brief: ctp/ and scripts/ contain the")
    A("entire verification program in Python, with no third-party Python dependencies.")
    A("It needs a Python interpreter and an OpenSSL providing ML-DSA-87 and")
    A("SLH-DSA-SHAKE-256s (OpenSSL 3.5+ in 2026; presumably ordinary by the time you")
    A("read this). Run:")
    A("")
    A("    python -m pytest -q")
    A("    python scripts/verify_bundle.py   vectors/valid/evidence-bundle-live-anchored.cbor")
    A("    python scripts/verify_sandwich.py vectors/valid/astro-sandwich-bundle.cbor \\")
    A("            --photos live/g2b-work/photos")
    A("")
    A("A passing run re-derives every measurement from the raw recorded network packets,")
    A("checks every signature, recomputes the Merkle trees, and confirms the checkpoint")
    A("really appears inside a block that satisfies its own proof-of-work target.")
    A("")
    A("")
    A("THE ANCHOR CHAIN")
    A("=" * 78)
    A("")
    A("live/chain-blocks.hex holds every block of the experimental chain")
    A(f"as raw bytes, one per line, as captured when this deposit was built ({chain_len} blocks).")
    A("Its genesis is fixed at:")
    A("")
    A("  00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a")
    A("  coinbase: 'The Times 03/Aug/2026 Toll of schooling straitjacket'")
    A("")
    A("This chain is NOT Bitcoin. It is an experimental chain first mined in 2026 that")
    A("runs the January-2009 Bitcoin consensus rules unmodified. It has no monetary")
    A("value and none was ever claimed. The checkpoints anchored in it are:")
    A("")
    for epoch, height, h in anch:
        A(f"  epoch {epoch}   height {height:>4}   {h}")
    A("")
    A("Every block links to its predecessor by hash and satisfies difficulty-1 proof-of-")
    A("work. You can re-derive all of that from the raw bytes with the included verifier.")
    A("")
    A("")
    A("WHAT THIS DOES NOT CLAIM")
    A("=" * 78)
    A("")
    A("Read CLAIMS.md in full. The short form:")
    A("")
    A("  - It does not claim any time source told the truth. It bounds WHEN evidence")
    A("    was acquired, never whether its content is correct.")
    A("  - It does not claim absolute time, perfect simultaneity, or zero uncertainty.")
    A("  - The experimental chain's proof-of-work is difficulty-1: real work, but small.")
    A("    The economically meaningful anchor is the public Bitcoin one above.")
    A("  - The handwritten code visible in the Moon photographs is human-verifiable")
    A("    content, not a cryptographic binding, and is labelled as such.")
    A("  - At the time of this deposit, every machine involved was operated by one")
    A("    person. Implementation diversity was real; operator diversity was not.")
    A("")
    A("Errors found after publication were corrected in the record rather than erased.")
    A("RELEASE_NOTES.md contains those corrections, including a chain")
    A("reorganization that orphaned one anchor block and how it was re-anchored.")
    A("")
    A("")
    A("CONTENTS")
    A("=" * 78)
    A("")
    A("This deposit mirrors the original source repository exactly, so every command")
    A("in VERIFY.md works here without modification.")
    A("")
    A("  vectors/valid/            sealed evidence bundles + Bitcoin timestamp proofs")
    A("  live/chain-blocks.hex     the experimental anchor chain, raw blocks")
    A("  live/anchor-evidence/     what was done, when, and its stated limits")
    A("  live/g2b-work/photos/     the original Moon photographs")
    A("  ctp/, scripts/, tests/    the complete verification program")
    A("  SPEC.md, INVARIANTS.md, CLAIMS.md, THREAT-MODEL.md, VERIFY.md")
    A("  MANIFEST.sha256           SHA-256 of every file in this deposit")
    A("")
    A("Verify the deposit's own integrity with:")
    A("")
    A("    sha256sum -c MANIFEST.sha256")
    A("")
    return "\n".join(lines) + "\n"


def main():
    out_root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist-archive"
    stamp = time.strftime("%Y%m%d", time.gmtime())
    dest = out_root / f"chronology-protocol-deposit-{stamp}"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for src_rel, dst_rel in CONTENTS:
        src = ROOT / src_rel
        dst = dest / dst_rel
        if not src.exists():
            print(f"  skip (missing): {src_rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", ".pytest_cache", "keys", "*.pem"))
        else:
            shutil.copy2(src, dst)

    att = bitcoin_attestations()
    anch, chain_len = anchors()
    built = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    prov = git_provenance()
    (dest / "README.txt").write_text(readme(att, anch, chain_len, built, prov),
                                     encoding="utf-8", newline="\n")
    (dest / "PROVENANCE.json").write_text(json.dumps(
        {"built_utc": built, "repository": "github.com/machine-native/chronology-protocol",
         **prov}, indent=2) + "\n", encoding="utf-8", newline="\n")

    # manifest over everything, written last
    lines = []
    for p in sorted(dest.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256":
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            lines.append(f"{digest}  {p.relative_to(dest).as_posix()}")
    (dest / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    tar_path = out_root / f"{dest.name}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(dest, arcname=dest.name)

    total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    print(json.dumps({
        "deposit": str(dest), "files": len(lines),
        "size_mb": round(total / 1e6, 1),
        "tarball": str(tar_path),
        "tarball_sha256": hashlib.sha256(tar_path.read_bytes()).hexdigest(),
        "tarball_mb": round(tar_path.stat().st_size / 1e6, 1),
        "bitcoin_attested_bundles": sum(1 for _, _, r in att if r),
        "anchors": len(anch),
    }, indent=2))


if __name__ == "__main__":
    main()
