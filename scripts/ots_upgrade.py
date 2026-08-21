#!/usr/bin/env python3
"""Minimal OpenTimestamps upgrader: pending calendar attestations -> Bitcoin.

For each FILE.ots, asks the recorded calendars for the completed timestamp of each
pending commitment and merges it in. After upgrade the proof contains a
BitcoinBlockHeaderAttestation and verifies against any Bitcoin node with a standard
OTS client — no calendar, and no trust in this project, needed thereafter.

Usage: python scripts/ots_upgrade.py FILE.ots [FILE.ots ...]
"""
import sys
from pathlib import Path

from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.timestamp import DetachedTimestampFile
from opentimestamps.core.notary import PendingAttestation, BitcoinBlockHeaderAttestation
from opentimestamps.core.serialize import (StreamSerializationContext,
                                           StreamDeserializationContext)


def upgrade(path: Path) -> bool:
    with path.open("rb") as f:
        detached = DetachedTimestampFile.deserialize(StreamDeserializationContext(f))
    ts = detached.timestamp
    changed = False

    def walk(node):
        yield node
        for child in node.ops.values():
            yield from walk(child)

    for node in list(walk(ts)):
        for attestation in list(node.attestations):
            if not isinstance(attestation, PendingAttestation):
                continue
            uri = attestation.uri if isinstance(attestation.uri, str) else attestation.uri.decode()
            try:
                fresh = RemoteCalendar(uri).get_timestamp(node.msg, timeout=20)
                node.merge(fresh)
                changed = True
                print(f"  {uri}: merged")
            except Exception as e:
                print(f"  {uri}: not ready / failed ({e})")
    heights = sorted({a.height for _, a in ts.all_attestations()
                      if isinstance(a, BitcoinBlockHeaderAttestation)})
    if changed:
        with path.open("wb") as f:
            detached.serialize(StreamSerializationContext(f))
    if heights:
        print(f"  BITCOIN ATTESTED: block height(s) {heights}")
        return True
    print("  still pending")
    return False


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    ok = True
    for a in sys.argv[1:]:
        print(a)
        ok = upgrade(Path(a)) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
