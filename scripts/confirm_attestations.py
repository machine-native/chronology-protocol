#!/usr/bin/env python3
"""Confirm every Bitcoin attestation in this repository against a block explorer.

An `.ots` proof makes a falsifiable claim of the form:

    block N's merkle root must be R

That claim is checkable by anyone, against any Bitcoin node or explorer, without
this repository's cooperation. This script does exactly that check and nothing
else: it reads the required (height, merkle root) pairs out of the proofs, asks
blockstream.info what each block's merkle root actually is, and compares.

Nothing here trusts the proof, the calendar server that issued it, or us. That
is the whole point -- if a proof and the blockchain disagree, the proof is
wrong, and this prints MISMATCH.

WHY UNREACHABLE IS NOT FAILURE

If the explorer cannot be reached the answer is INDETERMINATE, not FAIL, and the
exit code says so separately (2, not 1). "I could not check" and "I checked and
it was wrong" are different findings, and collapsing them is how a network
outage gets mistaken for a broken proof. This project has made that mistake once
already, in its own verifier, and it was the most serious defect outside review
found.

Usage:
    python scripts/confirm_attestations.py
    python scripts/confirm_attestations.py --explorer https://blockstream.info/api

Exit codes:  0 all confirmed · 1 at least one mismatch · 2 nothing wrong, but
             at least one block could not be checked
"""
from __future__ import annotations
import argparse, collections, json, pathlib, re, subprocess, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ATT = re.compile(
    r"BITCOIN block (\d+)\s*\n\s*that block's merkle root must be: ([0-9a-f]{64})")


def required_roots(proofs):
    """(height -> {merkle roots the proofs demand}, total attestation entries).

    The map is height -> SET, so proofs that disagree with EACH OTHER are caught
    before any explorer is asked. The separate total is kept because several
    proofs commonly attest to the same block, and collapsing them would report
    fewer attestations than the repository actually carries."""
    req = collections.defaultdict(set)
    total = 0
    for f in proofs:
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "ots_info.py"), str(f)],
                             capture_output=True, text=True).stdout
        for height, root in ATT.findall(out):
            req[int(height)].add(root)
            total += 1
    return req, total


def merkle_root_at(explorer: str, height: int) -> str:
    def get(url):
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read().decode().strip()
    return json.loads(get(f"{explorer}/block/{get(f'{explorer}/block-height/{height}')}"))["merkle_root"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--explorer", default="https://blockstream.info/api",
                    help="any explorer with the blockstream API shape; use one you trust")
    ap.add_argument("--vectors", default="vectors/valid")
    a = ap.parse_args()

    proofs = sorted((ROOT / a.vectors).glob("*.ots"))
    if not proofs:
        raise SystemExit(f"no .ots proofs under {a.vectors}")
    req, total = required_roots(proofs)

    print(f"{len(proofs)} proofs · {total} attestations · "
          f"{len(req)} distinct blocks\nasking {a.explorer}\n")

    ok = bad = indeterminate = 0
    for height in sorted(req):
        roots = req[height]
        if len(roots) != 1:
            print(f"  {height}  MISMATCH       proofs disagree among themselves: {sorted(roots)}")
            bad += 1
            continue
        want = next(iter(roots))
        try:
            actual = merkle_root_at(a.explorer, height)
        except Exception as e:
            print(f"  {height}  INDETERMINATE  explorer unreachable: {e}")
            indeterminate += 1
            continue
        if actual == want:
            print(f"  {height}  CONFIRMED      {actual}")
            ok += 1
        else:
            print(f"  {height}  MISMATCH       proof requires {want}")
            print(f"  {'':4}                 explorer reports {actual}")
            bad += 1

    print(f"\nconfirmed {ok} · mismatched {bad} · could not check {indeterminate}")
    if bad:
        print("\nA MISMATCH means a proof asserts something the blockchain does not.\n"
              "Trust the blockchain.")
        return 1
    if indeterminate:
        print("\nNo proof was contradicted, but not every block was checked.\n"
              "That is not the same as success. Re-run when the network is available.")
        return 2
    print("\nEvery attestation in this repository was confirmed against an explorer\n"
          "that has never heard of this project.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
