#!/usr/bin/env python3
"""G6 acquisition: rolling-code camera witness + fresh NTP round -> epoch-4 checkpoint.

What is different from G2b (epoch 2)
------------------------------------
G2b's frames carried a single HANDWRITTEN code. That proves the photographs were
taken after B0 existed, and nothing more: one code is one instant, and a stack of
frames all showing it could have been shot in two seconds.

G6 uses a code that changes every `slot_seconds`, displayed by
tools/rolling-code.html and derived from the same challenge:

    code(slot) = SHA-256("CHRN-ROLL/v1:" + SEED16 + ":" + slot)[:6 bytes]
    slot       = floor(unix_time / slot_seconds)

Frames spanning several slots therefore show several DIFFERENT codes, none of
which could have been computed before B0 was mined. That is what upgrades the
camera witness from "taken after B0" to "taken after B0, across real elapsed
time" -- while still being human-verifiable content rather than machine
cryptography.

What this program checks, and what it refuses
---------------------------------------------
It cannot read a code out of a JPEG; there is no OCR here and there should not
be. What it does is compute, from each frame's EXIF time, which code MUST have
been on the screen, and record that expectation in the evidence. The operator
compares it against the frames by eye.

It refuses a series that would not support the claim:

  * fewer than MIN_FRAMES frames
  * spanning less than MIN_SPAN_S seconds
  * covering fewer than MIN_SLOTS distinct slots

The third is the one that matters and the one a short series fails. Six frames
taken four seconds apart span two slots and show two codes -- which is barely
more than G2b already had. `--allow-weak` proceeds anyway, but records the
shortfall inside the evidence rather than letting a thin series look like a
strong one.

Usage:
    python scripts/run_g6.py                      # live/g6-work
    python scripts/run_g6.py --work live/g6b-work
    python scripts/run_g6.py --dry-run            # check frames, touch nothing
"""
from __future__ import annotations
import argparse, calendar, glob, hashlib, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import piexif
from run_sandwich import HOSTS, keypairs
from rolling_code import code_for
from ctp import cbor
from ctp.genesis import build_protocol_genesis
from ctp.model import (SignedCheckpoint, build_checkpoint, sign_checkpoint,
                       sign_observation)
from ctp.bitcoin_jan09 import anchor_payload
from ctp.pq import ensure_available
from ctp.sandwich import (challenge, exchange_nonce, ntp_exchange, derive_measurement,
                          evidence_blob, ntp_unsigned, camera_evidence_blob,
                          camera_unsigned, PS)

EPOCH = 4
PREV_WORK = "live/g5-work"                 # epoch 3
PLACE = "New Delhi, India (28.6139 N, 77.2090 E, operator-stated city)"
CAMERA = "samsung Galaxy M56 5G"
WITNESS_ID = "samsung-galaxy-m56-5g/parthod0x"
CLOCK_MARGIN_PS = 120 * PS                 # handheld phone clock, honest margin

MIN_FRAMES = 6
MIN_SPAN_S = 60
MIN_SLOTS = 4


def load_frames(work: Path, ist_offset_s: int):
    """Digest every original frame and read its self-asserted capture time."""
    paths = sorted(glob.glob(str(work / "photos" / "*.jpg")))
    if not paths:
        raise SystemExit(f"no frames in {work}/photos/ -- nothing to consolidate")
    photos, exif_ns = {}, {}
    for p in paths:
        name = Path(p).name
        photos[name] = hashlib.sha256(Path(p).read_bytes()).digest()
        ex = piexif.load(p)
        try:
            dto = ex["Exif"][piexif.ExifIFD.DateTimeOriginal].decode()
        except KeyError:
            raise SystemExit(
                f"{name} has no DateTimeOriginal. It was probably re-encoded in "
                "transit -- messaging apps and cloud sync strip EXIF. Copy the "
                "originals off the phone by USB.")
        sub = ex["Exif"].get(piexif.ExifIFD.SubSecTimeOriginal, b"0").decode()
        unix_utc = calendar.timegm(time.strptime(dto, "%Y:%m:%d %H:%M:%S")) - ist_offset_s
        frac_ns = int(int(sub) * 10 ** (9 - len(sub))) if sub.isdigit() else 0
        exif_ns[name] = unix_utc * 10**9 + frac_ns
    return photos, exif_ns


def rolling_expectation(exif_ns: dict, seed16: str, slot_s: int, code_frames=None):
    """Which code may have been on the screen in each frame.

    Recorded as an expectation, never a measurement: EXIF is the camera's own
    assertion, so this says "if the camera clock was right, the screen read one
    of these". A verifier confirms it by looking at the photograph.

    THE ACCEPTABLE SET IS THREE CODES, NOT ONE. Two independent clocks are
    involved -- the phone rendering the code and the camera stamping EXIF -- and
    the screen is captured a moment after it was painted. In this session's own
    frames, 20260823_211531 shows slot 178749992 while its EXIF falls in
    178749993: a real, benign, one-slot lag. tools/rolling-code.html and
    scripts/rolling_code.py both already document a +/-1 slot tolerance; a
    verifier handed a single expected code would read that frame as a mismatch
    and could reasonably conclude the series was fabricated.

    code_frames: names of frames that actually show the code page. Frames
    outside it -- sky-only shots, strays, anything taken before Start was
    pressed -- carry no expectation at all, because asserting one for a frame
    that cannot show a code invites exactly the false mismatch above.
    """
    rows = []
    for name in sorted(exif_ns, key=lambda n: exif_ns[n]):
        t = exif_ns[name] // 10**9
        slot = t // slot_s
        shows_code = code_frames is None or name in code_frames
        row = {
            "frame": name,
            "exif_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)),
            "slot": slot,
            "shows_code": shows_code,
        }
        if shows_code:
            row["expected_code"] = code_for(seed16, slot)
            row["acceptable_codes"] = {str(slot + d): code_for(seed16, slot + d)
                                       for d in (-1, 0, 1)}
        else:
            row["expected_code"] = None
            row["acceptable_codes"] = None
            row["reason"] = "frame does not show the code page"
        rows.append(row)
    return rows


def assess(rows, slot_s):
    """Thresholds count ONLY code-bearing frames.

    A session of three code frames and forty sky shots would otherwise sail past
    a frame count it has not earned: the sky shots say nothing about elapsed
    time, which is the entire claim the rolling code exists to support. The span
    is likewise measured across the code-bearing frames alone.
    """
    coded = [r for r in rows if r["shows_code"]]
    slots = {r["slot"] for r in coded}
    codes = {r["expected_code"] for r in coded}
    span_s = (max(slots) - min(slots)) * slot_s if coded else 0
    return {
        "frames_total": len(rows),
        "frames_with_code": len(coded),
        "span_seconds": span_s,
        "distinct_slots": len(slots),
        "distinct_codes": len(codes),
        "meets_min_frames": len(coded) >= MIN_FRAMES,
        "meets_min_span": span_s >= MIN_SPAN_S,
        "meets_min_slots": len(slots) >= MIN_SLOTS,
        "thresholds": {"min_frames": MIN_FRAMES, "min_span_s": MIN_SPAN_S,
                       "min_slots": MIN_SLOTS},
    }


def parse_code_frames(spec, all_names):
    """--code-frames accepts 'FIRST..LAST' or a comma-separated list.

    Which frames show the code page is something only the operator can know: a
    program cannot read a screen out of a JPEG, and this one deliberately does
    not try. Declaring it beats assuming every frame shows it, because a wrong
    assumption manufactures an expectation the photograph then contradicts --
    which reads exactly like a forged series.
    """
    if not spec:
        return None
    names = sorted(all_names)
    if ".." in spec:
        lo, hi = (x.strip() for x in spec.split("..", 1))
        sel = {n for n in names if lo <= n <= hi}
    else:
        sel = {x.strip() for x in spec.split(",") if x.strip()}
    unknown = sel - set(names)
    if unknown:
        raise SystemExit("--code-frames names frames that are not present: "
                         + repr(sorted(unknown)[:3]))
    if not sel:
        raise SystemExit("--code-frames selected no frames")
    return sel

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="live/g6-work")
    ap.add_argument("--ist-offset", type=int, default=5 * 3600 + 1800,
                    help="seconds the EXIF wall clock is ahead of UTC")
    ap.add_argument("--allow-weak", action="store_true",
                    help="proceed on a series below threshold, recording the shortfall")
    ap.add_argument("--dry-run", action="store_true",
                    help="report the frames and expected codes, write nothing")
    ap.add_argument("--code-frames", default=None,
                    help="which frames show the code page: 'FIRST..LAST' or a "
                         "comma-separated list. Others stay hashed and "
                         "witnessed but carry no code expectation.")
    a = ap.parse_args()

    work = ROOT / a.work
    ch = json.loads((work / "challenge.json").read_text())
    b0_hash, session_id = ch["b0_hash"], bytes.fromhex(ch["session_id"])
    q = challenge(b0_hash, session_id)
    if q.hex() != ch["challenge"]:
        raise SystemExit("challenge.json does not match its own B0 and session_id")
    seed16, slot_s = ch["seed16"], ch.get("slot_seconds", 10)

    photos, exif_ns = load_frames(work, a.ist_offset)
    times = sorted(exif_ns.values())
    code_frames = parse_code_frames(a.code_frames, exif_ns.keys())
    rows = rolling_expectation(exif_ns, seed16, slot_s, code_frames)
    verdict = assess(rows, slot_s)

    print(f"\nB0 height {ch['b0_height']}  seed {seed16}  slot {slot_s}s")
    print(f"{'frame':<12} {'exif UTC':<21} {'slot':<12} expected code")
    for r in rows:
        code = r['expected_code'] or '-- no code page in frame --'
        print(f"  {r['frame']:<22} {r['exif_utc']:<21} {r['slot']:<12} {code}")
    print(f"\n  frames {verdict['frames_total']} total, "
          f"{verdict['frames_with_code']} showing a code   "
          f"span {verdict['span_seconds']}s   "
          f"distinct slots {verdict['distinct_slots']}   "
          f"distinct codes {verdict['distinct_codes']}")
    print("  each code-bearing frame accepts its slot +/-1: two clocks are\n"
          "  involved, and the screen is captured a moment after it is painted.")

    failures = [k for k in ("meets_min_frames", "meets_min_span", "meets_min_slots")
                if not verdict[k]]
    if failures:
        msg = (f"\n  SERIES BELOW THRESHOLD: {', '.join(failures)}\n"
               f"  need >= {MIN_FRAMES} frames, >= {MIN_SPAN_S}s span, "
               f">= {MIN_SLOTS} distinct slots.\n"
               "  A series covering few slots shows few codes, which is close to\n"
               "  what a single handwritten code already proved. The point of the\n"
               "  rolling code is elapsed time, and this series barely shows any.")
        if not a.allow_weak:
            raise SystemExit(msg + "\n  Re-shoot, or pass --allow-weak to record "
                                   "the shortfall in the evidence.\n")
        print(msg + "\n  --allow-weak given: proceeding, and recording the shortfall.\n")

    if a.dry_run:
        print("  dry run: nothing written.\n")
        return

    ensure_available()
    origin_s = (int(time.time()) // 86400) * 86400
    mid_ns = (times[0] + times[-1]) // 2
    unc_ns = (times[-1] - times[0]) // 2 + CLOCK_MARGIN_PS // 1000

    cam_blob = camera_evidence_blob(photos, exif_ns, CAMERA, PLACE,
                                    mid_ns, unc_ns, q, b0_hash, session_id)

    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()

    print("  fresh NTP round on the same challenge:")
    exchanges = {}
    for seq in (0, 1):
        for host in HOSTS:
            if seq == 1 and host not in exchanges:
                continue
            nonce = exchange_nonce(q, host, seq)
            try:
                ex = ntp_exchange(host, nonce)
            except Exception as e:
                print(f"    {host} seq {seq}: FAILED ({e})")
                exchanges.pop(host, None)
                continue
            if ex["response"][24:32] != nonce:
                exchanges.pop(host, None)
                continue
            meas = derive_measurement(ex)
            exchanges.setdefault(host, {})[seq] = (ex, meas,
                                                   evidence_blob(seq, ex, q, b0_hash, session_id))
            print(f"    {host} seq {seq}: ok rtt {meas['rtt_ps']/1e9:.0f}ms")
    complete = {h: r for h, r in exchanges.items() if 0 in r and 1 in r}
    if len(complete) < 3:
        raise SystemExit("too few NTP witnesses completed both rounds")

    history, latest, blobs = [], [], []
    wkeys = {h: keypairs(work / "keys", h.replace(".", "-")) for h in complete}
    for host in sorted(complete):
        ex0, m0, b0b = complete[host][0]
        ex1, m1, b1b = complete[host][1]
        u0 = ntp_unsigned(0, ex0, m0, b0b, gid, None, origin_s)
        s0 = sign_observation(u0, wkeys[host])
        u1 = ntp_unsigned(1, ex1, m1, b1b, gid, u0.lineage_id(), origin_s)
        s1 = sign_observation(u1, wkeys[host])
        history += [s0, s1]
        latest.append(s1)
        blobs += [b0b, b1b]

    cam_u = camera_unsigned(cam_blob, WITNESS_ID, gid, origin_s, time.monotonic_ns())
    cam_s = sign_observation(cam_u, keypairs(work / "keys", "camera"))
    history.append(cam_s)
    latest.append(cam_s)
    blobs.append(cam_blob)

    prev = SignedCheckpoint.from_obj(
        cbor.loads((ROOT / PREV_WORK / "checkpoint.cbor").read_bytes()))
    if prev.unsigned.epoch != EPOCH - 1:
        raise SystemExit(f"{PREV_WORK} is epoch {prev.unsigned.epoch}, "
                         f"expected {EPOCH - 1}")
    cp = build_checkpoint(EPOCH, latest, f=1, previous=prev.record_commitment())
    scp = sign_checkpoint(cp, keypairs(work / "keys", "checkpoint"))
    commitment = scp.record_commitment()
    payload = anchor_payload(cp.epoch, commitment.sha256, commitment.shake384)

    for i, blob in enumerate(blobs):
        (work / f"blob{i:02d}.cbor").write_bytes(blob)
    (work / "history.cbor").write_bytes(cbor.dumps([s.as_obj() for s in history]))
    (work / "checkpoint.cbor").write_bytes(scp.canonical())
    (work / "payload.hex").write_text(payload.hex() + "\n", newline="\n")
    (work / "photo-manifest.json").write_text(json.dumps(
        {k: v.hex() for k, v in sorted(photos.items())}, indent=1) + "\n", newline="\n")
    (work / "rolling-expectation.json").write_text(json.dumps({
        "label": "EXPECTATION_NOT_EVIDENCE",
        "note": "Which code must have been on the screen in each frame IF the "
                "camera clock was right. EXIF is the camera's own assertion; the "
                "sandwich, not EXIF, carries the causal claim. A verifier confirms "
                "this by looking at the photographs.",
        "seed16": seed16,
        "slot_seconds": slot_s,
        "b0_height": ch["b0_height"],
        "frames": rows,
        "assessment": verdict,
        "below_threshold": bool(failures),
        "shortfall": failures,
    }, indent=1) + "\n", newline="\n")

    print(json.dumps({
        "epoch": cp.epoch,
        "witnesses": sorted(complete) + [f"CAMERA {WITNESS_ID}"],
        "frames": len(photos),
        "distinct_codes": verdict["distinct_codes"],
        "below_threshold": bool(failures),
        "checkpoint_sha256": commitment.sha256.hex(),
        "payload_hex": payload.hex(),
    }, indent=2))
    print("\n  Next: mine B1 carrying this payload, then assemble the bundle.\n")


if __name__ == "__main__":
    main()
