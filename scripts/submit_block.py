#!/usr/bin/env python3
"""Broadcast a mined block to the anchor chain.

Separate from the miner on purpose. Mining a block is a local, reversible act:
if it is wrong, delete the file. Broadcasting it is neither — it goes to every
peer, and a chain does not forget. Keeping the two in different programs means
no mistake in the first can silently become a mistake in the second.

Usage:
  python scripts/submit_block.py live/mine/fpga-block-273-0000....json
  python scripts/submit_block.py <file> --yes          # skip the confirmation

Before sending anything it re-derives the proof-of-work from the raw bytes in
the file. It does not trust the miner's own claim that the block is valid --
that claim is what is being checked.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.bitcoin_jan09 import block_hash, target_from_bits, parse_single_tx_block


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("block_json", help="a file written by fpga_host.py mine")
    ap.add_argument("--host", default="bitcoin.bitcoin-lab.org")
    ap.add_argument("--port", type=int, default=18026)
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    ap.add_argument("--check-only", action="store_true",
                    help="validate the file and exit without contacting anything")
    a = ap.parse_args()

    p = Path(a.block_json)
    if not p.is_file():
        raise SystemExit(f"no such file: {p}")
    rec = json.loads(p.read_text())
    raw = bytes.fromhex(rec["raw_block_hex"])

    # Re-derive everything from the bytes. The JSON's own fields are treated as
    # claims to be checked, not as facts -- including the hash it states.
    header = raw[:80]
    h = block_hash(header)
    bits = int.from_bytes(header[72:76], "little")
    target = target_from_bits(bits)
    value = int(h, 16)

    print(f"file      {p}")
    print(f"height    {rec.get('height')}   (claimed; the network decides)")
    print(f"hash      {h}")
    print(f"bits      {hex(bits)}")
    print(f"size      {len(raw)} bytes")

    if h != rec.get("hash"):
        raise SystemExit(f"\nREFUSING: the file claims hash {rec.get('hash')} but its "
                         f"own bytes hash to {h}. The file is inconsistent.")
    if value > target:
        raise SystemExit(f"\nREFUSING: proof-of-work is not valid.\n"
                         f"  hash   {value:064x}\n  target {target:064x}")
    try:
        parse_single_tx_block(raw)
    except Exception as e:
        raise SystemExit(f"\nREFUSING: block does not parse as a single-tx block: {e}")
    print("pow       VALID (re-derived here from the raw bytes)")

    if a.check_only:
        print("\n--check-only: nothing was sent.")
        return

    print(f"\nThis will broadcast the block to {a.host}:{a.port}.")
    print("Broadcasting is irreversible and visible to every peer on the chain.")
    if not a.yes:
        try:
            if input("Type 'submit' to send: ").strip() != "submit":
                print("Not sent.")
                return
        except EOFError:
            raise SystemExit("No terminal to confirm on; pass --yes if you mean it.")

    from ctp.p2p_v01 import submit_block
    events = submit_block(a.host, a.port, raw)
    print(json.dumps(events, indent=2) if events else "(no events returned)")

    print("\nA successful send is NOT proof of acceptance -- the peer may reject the")
    print("block for a reason it never reports. Confirm it is actually on the chain:")
    print("    python live/fetch_full_chain.py")
    print(f"and look for {h}")


if __name__ == "__main__":
    main()
