#!/usr/bin/env python3
"""Show what an OpenTimestamps proof asserts, so you can check it against Bitcoin yourself.

Uses NO third-party packages — the proof parser is `ctp/ots.py`, written from the
format specification precisely so that a cold-storage reader never needs a package
index. (An independent verifier found the earlier version importing the reference
library while the deposit claimed to be self-contained. They were right; this is
the fix.)

This is NOT a replacement for `ots verify`. The official client talks to a Bitcoin
node and confirms the commitment for you. This prints the same facts in a form you
can check by hand against any Bitcoin node or block explorer you already trust:

    for each Bitcoin attestation in the proof:
        the block height, and
        the 32-byte value that must appear as that block's MERKLE ROOT

If the merkle root of that Bitcoin block equals the value printed here, then the
file digest was committed before that block was mined — regardless of anything this
project says. That is the whole claim.

Usage: python scripts/ots_info.py FILE.ots [FILE.ots ...]
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.ots import parse_file, OTSError


def show(path: Path) -> bool:
    try:
        proof = parse_file(path)
    except OTSError as e:
        print(f"{path.name}\n  NOT A VALID PROOF: {e}")
        return False

    print(f"{path.name}")
    print(f"  file digest ({proof.file_hash_op}): {proof.file_digest.hex()}")

    target = path.with_suffix("") if path.suffix == ".ots" else None
    if target and target.is_file():
        actual = hashlib.sha256(target.read_bytes()).digest()
        match = actual == proof.file_digest
        print(f"  {target.name} on disk matches this proof: {match}")
        if not match:
            print("  *** the file next to this proof is NOT the file that was stamped ***")
            return False

    for height, merkle_root in proof.bitcoin:
        print(f"  BITCOIN block {height}")
        print(f"    that block's merkle root must be: {merkle_root}")
    for uri in proof.pending:
        print(f"  PENDING at {uri} (not yet in a Bitcoin block; run ots_upgrade.py later)")

    if proof.bitcoin:
        print("  check it yourself: compare each merkle root above against that block")
        print("  height on any Bitcoin node or explorer you trust. Nothing here asks")
        print("  you to trust us.")
        return True
    print("  no Bitcoin attestation yet — the calendars have not aggregated this")
    print("  commitment into a transaction. Run scripts/ots_upgrade.py later.")
    return False


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    ok = True
    for a in sys.argv[1:]:
        ok = show(Path(a)) and ok
        print()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
