#!/usr/bin/env python3
"""Judge the published first-retarget prediction against the chain's own bytes.

WHAT THIS IS FOR

On 2026-08-21, at height 272, the laboratory published a prediction about an event
that had not happened yet (`bitcoin-findings/PREDICTION-first-retarget.md`):

    The first retarget will change nothing. nBits will remain 0x1d00ffff.

    It will be computed, logged by the client as a RETARGET ***** event, and then
    discarded by a clamp -- the chain's difficulty is already at its floor.

ADR-0005 makes capturing that event the first item of Phase D, and the last of the
nine completion criteria. A prediction published in advance is only worth something
if it is judged afterwards by something other than its author's recollection.

So this script does not ask whether the prediction "looks right". It re-implements
`GetNextWorkRequired` from the released 2009 source -- including the 2015-block
off-by-one and the proof-of-work-limit clamp -- computes what nBits block 2016
*must* carry, and compares that against what the chain actually says.

THREE OUTCOMES

    HELD          the chain reached 2016 and nBits is what was predicted
    FAILED        the chain reached 2016 and nBits is not what was predicted
    NOT_YET       the chain has not reached 2016; nothing is judged

NOT_YET is not a pass. Running this early tells you how far away the event is and
nothing whatever about the prediction.

    python live/capture_retarget.py                 # use the local chain dump
    python live/capture_retarget.py --refresh       # re-download the chain first

Exit codes:  0 held - 1 failed - 2 not yet (or the chain could not be read)
"""
from __future__ import annotations
import argparse, hashlib, json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHAIN = HERE / "chain-blocks.hex"

# From derivatives/bitcoin/src/main.cpp, unmodified 2009 code.
N_TARGET_TIMESPAN = 14 * 24 * 60 * 60      # two weeks
N_TARGET_SPACING = 10 * 60
N_INTERVAL = N_TARGET_TIMESPAN // N_TARGET_SPACING          # 2016
PROOF_OF_WORK_LIMIT_BITS = 0x1D00FFFF
PREDICTED_BITS = 0x1D00FFFF
GENESIS = "00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a"


def dsha(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def bits_to_target(bits: int) -> int:
    """CBigNum::SetCompact."""
    size = bits >> 24
    word = bits & 0x007FFFFF
    if size <= 3:
        return word >> (8 * (3 - size))
    return word << (8 * (size - 3))


def target_to_bits(target: int) -> int:
    """CBigNum::GetCompact."""
    size = (target.bit_length() + 7) // 8
    if size <= 3:
        compact = target << (8 * (3 - size))
    else:
        compact = target >> (8 * (size - 3))
    if compact & 0x00800000:          # keep it positive, as the original does
        compact >>= 8
        size += 1
    return compact | (size << 24)


def parse_header(raw: bytes):
    ver, prev, merkle, ntime, bits, nonce = struct.unpack("<I32s32sIII", raw[:80])
    return {"version": ver, "prev": prev[::-1].hex(), "merkle_root": merkle[::-1].hex(),
            "nTime": ntime, "nBits": bits, "nNonce": nonce,
            "hash": dsha(raw[:80])[::-1].hex()}


# The genesis, which the dump does not carry. Its nTime is the published header
# value. It matters: the walk-back from height 2015 lands on height 0, so the very
# first retarget measures nTime(2015) - nTime(genesis). Indexing the dump from 1
# and forgetting this is an off-by-one that only shows up on the one block the
# whole exercise is about -- it was made here first, and caught by
# tests/test_retarget_rule.py before the event rather than after.
GENESIS_HEADER = {"nTime": 1785781375, "nBits": 0x1D00FFFF, "hash": GENESIS,
                  "height": 0, "note": "not in the dump; published header values"}


def load_chain():
    """Indexed BY HEIGHT: index 0 is the genesis, index h is the block at height h."""
    if not CHAIN.is_file():
        return None
    out = [dict(GENESIS_HEADER)]
    for line in CHAIN.read_text(encoding="utf-8").split():
        if line:
            out.append(parse_header(bytes.fromhex(line)))
    return out


def next_work_required(headers, height_of_last: int):
    """GetNextWorkRequired for the block AFTER height_of_last.

    Returns (bits, detail). `headers` is indexed by height: headers[h] is the
    block at height h, and headers[0] is the genesis.
    """
    last = headers[height_of_last]
    if (height_of_last + 1) % N_INTERVAL != 0:
        return last["nBits"], {"retarget": False,
                               "reason": f"(height+1) % {N_INTERVAL} != 0"}

    # The walk back is nInterval-1 blocks -- 2015, not 2016. This is the original
    # off-by-one, preserved unmodified, so the measured span covers 2015 intervals.
    first_height = height_of_last - (N_INTERVAL - 1)
    first = headers[first_height] if 0 <= first_height < len(headers) else None
    if first is None:
        return None, {"retarget": True, "reason": "walk-back ran past the genesis"}

    actual = last["nTime"] - first["nTime"]
    clamped = max(N_TARGET_TIMESPAN // 4, min(N_TARGET_TIMESPAN * 4, actual))

    new_target = bits_to_target(last["nBits"]) * clamped // N_TARGET_TIMESPAN
    limit = bits_to_target(PROOF_OF_WORK_LIMIT_BITS)
    clamped_to_limit = new_target > limit
    if clamped_to_limit:
        new_target = limit

    return target_to_bits(new_target), {
        "retarget": True,
        "first_height": first_height, "first_nTime": first["nTime"],
        "last_height": height_of_last, "last_nTime": last["nTime"],
        "nActualTimespan": actual,
        "nActualTimespan_after_bounds": clamped,
        "nTargetTimespan": N_TARGET_TIMESPAN,
        "bounds_applied": clamped != actual,
        "clamped_to_proof_of_work_limit": clamped_to_limit,
        "off_by_one_note": (f"the span covers {N_INTERVAL - 1} intervals, not "
                            f"{N_INTERVAL}; the 2009 walk-back is nInterval-1"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true",
                    help="re-download the chain from the public seed first")
    ap.add_argument("--out", default=None, help="write the evidence record here")
    a = ap.parse_args()

    if a.refresh:
        print("  fetching the chain from the public seed ...")
        r = subprocess.run([sys.executable, str(HERE / "fetch_full_chain.py")],
                           cwd=ROOT, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            print("  could not refresh the chain:\n" + (r.stderr or r.stdout)[-600:])
            return 2

    headers = load_chain()
    if not headers:
        print(f"\n  NOT_YET (chain not readable)\n  {CHAIN} is absent or empty."
              "\n  Run with --refresh.\n")
        return 2

    tip_height = len(headers) - 1     # headers[0] is the genesis
    print(f"\nfirst-retarget capture  ({time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})\n")
    print(f"  chain dump      heights 1..{tip_height}")

    if tip_height < N_INTERVAL:
        remaining = N_INTERVAL - tip_height
        span = headers[-1]["nTime"] - headers[1]["nTime"]
        rate = (tip_height - 1) / (span / 86400) if span > 0 else 0
        eta = remaining / rate if rate > 0 else float("inf")
        print(f"  retarget at     {N_INTERVAL}")
        print(f"  still to go     {remaining} blocks")
        if rate:
            print(f"  observed rate   {rate:.1f} blocks/day over the whole dump")
            print(f"  projection      roughly {eta:.0f} days away")
        print(f"\n  NOT_YET — nothing about the prediction is judged by this run.")
        print("  A projection is not a result, and this dump may itself be stale;")
        print("  use --refresh before reading the numbers as current.\n")
        return 2

    # The chain has reached the boundary. Judge it.
    predicted_bits, detail = next_work_required(headers, N_INTERVAL - 1)
    actual = headers[N_INTERVAL]            # height 2016
    actual_bits = actual["nBits"]
    prev_bits = headers[N_INTERVAL - 1]["nBits"]

    print(f"  height {N_INTERVAL - 1:<8} nBits 0x{prev_bits:08x}")
    print(f"  height {N_INTERVAL:<8} nBits 0x{actual_bits:08x}   <- the first retarget")
    print()
    for k, v in detail.items():
        print(f"    {k:<34} {v}")
    print()
    print(f"  recomputed from the 2009 rule   0x{predicted_bits:08x}")
    print(f"  published prediction            0x{PREDICTED_BITS:08x} (unchanged)")
    print(f"  the chain actually carries      0x{actual_bits:08x}")

    rule_ok = predicted_bits == actual_bits
    pred_ok = actual_bits == PREDICTED_BITS

    record = {
        "record_type": "first_retarget_capture",
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "interval": N_INTERVAL,
        "height_2015_nBits": f"0x{prev_bits:08x}",
        "height_2016_nBits": f"0x{actual_bits:08x}",
        "height_2016_hash": actual["hash"],
        "recomputed_nBits": f"0x{predicted_bits:08x}",
        "published_prediction_nBits": f"0x{PREDICTED_BITS:08x}",
        "prediction_source": "bitcoin-findings/PREDICTION-first-retarget.md (2026-08-21, height 272)",
        "rule_reimplementation_agrees_with_chain": rule_ok,
        "prediction_held": pred_ok,
        "detail": detail,
        "not_established": [
            "the client's own RETARGET ***** log line, which is separate evidence and "
            "must be captured from the running node; this script reads chain bytes only",
        ],
    }
    out = Path(a.out) if a.out else HERE / "anchor-evidence" / "first-retarget.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n  written to {out.relative_to(ROOT)}")

    if not rule_ok:
        print("\n  FAILED — the re-implemented 2009 rule does not agree with the chain.")
        print("  That is a finding about this chain or about this re-implementation,")
        print("  and either way it is the interesting outcome. Do not paper over it.\n")
        return 1
    if not pred_ok:
        print("\n  FAILED — the rule agrees with the chain, and the chain disagrees")
        print("  with what was predicted in August. The prediction was wrong, and the")
        print("  record should say so plainly, beside the original.\n")
        return 1

    print("\n  HELD — nBits is unchanged at the proof-of-work limit, exactly as")
    print("  predicted on 2026-08-21 at height 272, before the event.")
    print("\n  Still outstanding for the closing record: the client's own")
    print("  RETARGET ***** log line. This script reads chain bytes; the log is the")
    print("  node's own account of computing the value and discarding it.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
