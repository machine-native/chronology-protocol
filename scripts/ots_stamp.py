#!/usr/bin/env python3
"""Minimal OpenTimestamps stamper (external-anchor attestation, sidecar class).

Creates standard .ots detached timestamp proofs for the given files by submitting
their (nonced) SHA-256 commitments to public OpenTimestamps calendars. The
resulting proofs are PENDING calendar attestations; calendars aggregate into a
real Bitcoin transaction within hours, after which any standard OTS client can
upgrade the proof to a Bitcoin block attestation (`ots upgrade FILE.ots`) and
verify it against a Bitcoin node — no trust in this project required.

Rationale: the laboratory anchor chain gives the sandwich mechanical causal
bounds; an OpenTimestamps proof adds an economically real upper bound on the
same bytes from the public Bitcoin chain. This is a sidecar evidence class —
the CBOR bundles are not modified.

Usage: python scripts/ots_stamp.py FILE [FILE...]   (writes FILE.ots next to each)
"""
import os, sys
from pathlib import Path

from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile
from opentimestamps.core.op import OpSHA256, OpAppend
from opentimestamps.core.serialize import StreamSerializationContext

CALENDARS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://a.pool.eternitywall.com",
    "https://ots.btc.catallaxy.com",
]
MIN_ATTESTATIONS = 2


def stamp(path: Path) -> Path:
    with path.open("rb") as f:
        detached = DetachedTimestampFile.from_fd(OpSHA256(), f)
    # standard client practice: append a random nonce then hash, so calendars
    # never learn the bare file digest
    nonce_ts = detached.timestamp.ops.add(OpAppend(os.urandom(16)))
    merkle_tip = nonce_ts.ops.add(OpSHA256())
    got = 0
    for url in CALENDARS:
        try:
            resp = RemoteCalendar(url).submit(merkle_tip.msg, timeout=15)
            merkle_tip.merge(resp)
            got += 1
            print(f"  {url}: ok")
        except Exception as e:
            print(f"  {url}: failed ({e})")
    if got < MIN_ATTESTATIONS:
        raise SystemExit(f"only {got} calendar attestations; need >= {MIN_ATTESTATIONS}")
    out = path.with_name(path.name + ".ots")
    with out.open("wb") as f:
        detached.serialize(StreamSerializationContext(f))
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for arg in sys.argv[1:]:
        p = Path(arg)
        print(p)
        out = stamp(p)
        print(f"  -> {out} ({out.stat().st_size} bytes, pending; upgrade later with a standard OTS client)")


if __name__ == "__main__":
    main()
