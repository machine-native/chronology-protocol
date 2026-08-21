#!/usr/bin/env python3
"""Show what an OpenTimestamps proof asserts, so you can check it against Bitcoin yourself.

This is NOT a replacement for `ots verify`. The official client talks to a Bitcoin node
and confirms the commitment for you. This prints the same facts in a form you can check
by hand against any Bitcoin node or block explorer you already trust:

    for each Bitcoin attestation in the proof:
        the block height, and
        the 32-byte value that must appear as that block's MERKLE ROOT

If the merkle root of that Bitcoin block equals the value printed here, then the file
digest was committed before that block was mined — regardless of anything this project
says. That is the whole claim.

It exists because the official `ots` CLI depends on python-bitcoinlib, which fails to
load on Windows (it dlopens libssl through ctypes). The `opentimestamps` library itself
works everywhere, so this uses only that.

Usage: python scripts/ots_info.py FILE.ots [FILE.ots ...]
"""
import hashlib
import sys
from pathlib import Path

from opentimestamps.core.timestamp import DetachedTimestampFile
from opentimestamps.core.notary import (BitcoinBlockHeaderAttestation,
                                        PendingAttestation)
from opentimestamps.core.serialize import StreamDeserializationContext


def walk(node):
    yield node
    for child in node.ops.values():
        yield from walk(child)


def show(path: Path) -> bool:
    with path.open("rb") as f:
        detached = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))
    target = path.with_suffix("") if path.suffix == ".ots" else None
    print(f"{path.name}")
    print(f"  file digest ({detached.file_hash_op.TAG_NAME}): {detached.file_digest.hex()}")
    if target and target.is_file():
        actual = hashlib.sha256(target.read_bytes()).digest()
        match = actual == detached.file_digest
        print(f"  {target.name} on disk matches this proof: {match}")
        if not match:
            print("  *** the file next to this proof is NOT the file that was stamped ***")
            return False

    attested = False
    for node in walk(detached.timestamp):
        for att in node.attestations:
            if isinstance(att, BitcoinBlockHeaderAttestation):
                print(f"  BITCOIN block {att.height}")
                print(f"    that block's merkle root must be: {node.msg[::-1].hex()}")
                attested = True
            elif isinstance(att, PendingAttestation):
                uri = att.uri if isinstance(att.uri, str) else att.uri.decode()
                print(f"  PENDING at {uri} (not yet in a Bitcoin block; run ots_upgrade.py later)")
    if attested:
        print("  check it yourself: compare each merkle root above against that block")
        print("  height on any Bitcoin node or explorer you trust. Nothing here asks")
        print("  you to trust us.")
    else:
        print("  no Bitcoin attestation yet — the calendars have not aggregated this")
        print("  commitment into a transaction. Run scripts/ots_upgrade.py later.")
    return attested


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
