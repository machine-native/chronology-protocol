#!/usr/bin/env python3
"""G2b acquisition consolidation: camera witness + fresh NTP round -> epoch-2 checkpoint.

Uses the standing challenge from live/g2b-work/challenge.json (issued against B0
before the photographs were taken; the code derived from it is handwritten inside
the frames). Adds a fresh NTP witness round bound to the same challenge, builds the
single-record camera witness over the original photo files, and produces the epoch-2
checkpoint (chained to the epoch-1 sandwich checkpoint) and its anchor payload.
"""
from __future__ import annotations
import glob, hashlib, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import piexif
from run_sandwich import HOSTS, keypairs
from ctp import cbor
from ctp.genesis import build_protocol_genesis
from ctp.model import build_checkpoint, sign_checkpoint, sign_observation
from ctp.bitcoin_jan09 import anchor_payload
from ctp.pq import ensure_available
from ctp.sandwich import (challenge, exchange_nonce, ntp_exchange, derive_measurement,
                          evidence_blob, ntp_unsigned, camera_evidence_blob,
                          camera_unsigned, SandwichBundle, PS)

IST_OFFSET_S = 5 * 3600 + 1800
PLACE = "New Delhi, India (28.6139 N, 77.2090 E, operator-stated city)"
CLOCK_MARGIN_PS = 120 * PS               # handheld phone clock, honest margin


def main():
    ensure_available()
    work = ROOT / "live" / "g2b-work"
    ch = json.loads((work / "challenge.json").read_text())
    b0_hash, session_id = ch["b0_hash"], bytes.fromhex(ch["session_id"])
    q = challenge(b0_hash, session_id)
    assert q.hex() == ch["challenge"], "challenge mismatch"
    origin_s = (int(time.time()) // 86400) * 86400

    # ---- camera witness over the original frames ----
    photos, exif_ns = {}, {}
    for p in sorted(glob.glob(str(work / "photos" / "*.jpg"))):
        name = Path(p).name
        photos[name] = hashlib.sha256(Path(p).read_bytes()).digest()
        ex = piexif.load(p)
        dto = ex["Exif"][piexif.ExifIFD.DateTimeOriginal].decode()
        sub = ex["Exif"].get(piexif.ExifIFD.SubSecTimeOriginal, b"0").decode()
        import calendar
        t = time.strptime(dto, "%Y:%m:%d %H:%M:%S")
        unix_utc = calendar.timegm(t) - IST_OFFSET_S      # EXIF wall time is IST
        frac_ns = int(int(sub) * 10 ** (9 - len(sub))) if sub.isdigit() else 0
        exif_ns[name] = unix_utc * 10**9 + frac_ns
    times = sorted(exif_ns.values())
    mid_ns = (times[0] + times[-1]) // 2
    unc_ns = (times[-1] - times[0]) // 2 + CLOCK_MARGIN_PS // 1000
    print(f"capture window UTC: {time.strftime('%H:%M:%S', time.gmtime(times[0]/1e9))}"
          f" - {time.strftime('%H:%M:%S', time.gmtime(times[-1]/1e9))}"
          f"  claimed mid ±{unc_ns/1e9:.0f}s")

    cam_blob = camera_evidence_blob(photos, exif_ns, "samsung Galaxy M56 5G", PLACE,
                                    mid_ns, unc_ns, q, b0_hash, session_id)

    genesis = build_protocol_genesis((ROOT / "SPEC.md").read_bytes(),
                                     (ROOT / "INVARIANTS.md").read_bytes())
    gid = genesis.genesis_id()

    # ---- fresh NTP round on the same challenge ----
    exchanges = {}
    for seq in (0, 1):
        for host in HOSTS:
            if seq == 1 and host not in exchanges:
                continue
            nonce = exchange_nonce(q, host, seq)
            try:
                ex = ntp_exchange(host, nonce)
            except Exception as e:
                print(f"  {host} seq {seq}: FAILED ({e})")
                exchanges.pop(host, None)
                continue
            if ex["response"][24:32] != nonce:
                exchanges.pop(host, None)
                continue
            meas = derive_measurement(ex)
            blob = evidence_blob(seq, ex, q, b0_hash, session_id)
            exchanges.setdefault(host, {})[seq] = (ex, meas, blob)
            print(f"  {host} seq {seq}: ok rtt {meas['rtt_ps']/1e9:.0f}ms")
    complete = {h: r for h, r in exchanges.items() if 0 in r and 1 in r}
    if len(complete) < 3:
        raise SystemExit("too few NTP witnesses")

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

    cam_u = camera_unsigned(cam_blob, "samsung-galaxy-m56-5g/parthod0x", gid, origin_s,
                            time.monotonic_ns())
    cam_s = sign_observation(cam_u, keypairs(work / "keys", "camera"))
    history.append(cam_s)
    latest.append(cam_s)
    blobs.append(cam_blob)

    prev_bundle = SandwichBundle.from_bytes(
        (ROOT / "vectors" / "valid" / "reality-sandwich-bundle.cbor").read_bytes())
    previous = prev_bundle.checkpoint.record_commitment()
    cp = build_checkpoint(2, latest, f=1, previous=previous)
    scp = sign_checkpoint(cp, keypairs(work / "keys", "checkpoint"))
    commitment = scp.record_commitment()
    payload = anchor_payload(cp.epoch, commitment.sha256, commitment.shake384)

    for i, blob in enumerate(blobs):
        (work / f"blob{i:02d}.cbor").write_bytes(blob)
    (work / "history.cbor").write_bytes(cbor.dumps([s.as_obj() for s in history]))
    (work / "checkpoint.cbor").write_bytes(scp.canonical())
    (work / "payload.hex").write_text(payload.hex() + "\n")
    (work / "photo-manifest.json").write_text(json.dumps(
        {k: v.hex() for k, v in sorted(photos.items())}, indent=1) + "\n")

    print(json.dumps({
        "witnesses": sorted(complete) + ["CAMERA samsung-galaxy-m56-5g"],
        "history_records": len(history),
        "consensus": {"verdict": cp.verdict, "q": cp.q, "f": cp.f, "witnesses": cp.witness_count,
                      "interval_ps": None if cp.interval is None else [cp.interval.lower, cp.interval.upper]},
        "camera_claimed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mid_ns / 1e9)),
        "checkpoint_epoch": cp.epoch,
        "payload_hex": payload.hex(),
    }, indent=2))


if __name__ == "__main__":
    main()
