# The First Astronomical ChronologyProof — height 253, 2026-08-20

A real optical observation of the Moon, causally sandwiched between live proof-of-work
blocks, checkpointed with post-quantum signatures beside network-time witnesses, and
compared against a deterministic celestial-model expectation. Observer and operator:
parthod0x, New Delhi, India. The authoritative artifact is
`vectors/valid/astro-sandwich-bundle.cbor` (offline verifier:
`scripts/verify_sandwich.py BUNDLE --photos DIR`).

## The sandwich

```
B0   0000000058e3ceb8b0a3f332d9ec7248884d7693125f7e80972fbd8bccc6f6b9   height 252
       challenge issued 2026-08-20T15:19:01Z
       q = d2b79b45d60f408a3aab7c9bbb5c507b092d150f38f5f2e00a8889b6de56de52
       its first 16 hex digits, D2B79B45D60F408A, handwritten on paper
  ≺  observation   2026-08-20 15:24:12 – 15:29:20 UTC (EXIF, Samsung Galaxy M56 5G)
       ten original frames, sha256-manifested:
         3 frames: gibbous Moon and the handwritten code IN THE SAME FRAME
         3 frames: the Moon alone, through monsoon clouds
         3 frames: the code close-up          1 frame: paper + faint Moon
       + five fresh NTPv4 witness rounds (NIST, PTB, Google, Microsoft, Apple),
         challenge nonce embedded and echoed, same session
  ≺
C    00000000eafb36b7c47b0a9ac975595b3e5ecc7006c85757bf5008380affe3ee   height 253
       nNonce 605453534, real difficulty-1 work, parent = B0 (adjacent-block window)
       payload: epoch-2 checkpoint over 6 witnesses (5 NTP + 1 camera),
       chained to the epoch-1 sandwich checkpoint, which chains to sealed epoch 0
  ≺
B1…  heights 254-263 mined overnight by the laboratory's own miner — burial 10 at
       assembly, growing
```

## Prediction vs observation

The bundle carries the open-astrolabe engine's expectation for the capture midpoint
over New Delhi (`prediction_json`, label `EXPECTATION_NOT_EVIDENCE`):

```
predicted  azimuth 216.6° (SW)   altitude 24.0°   illuminated fraction 0.552
           Sun 24.4° below horizon (night)        engine grade: reference (10″)
observed   a gibbous Moon of visibly ~half-lit phase, mid-low in a southwest
           street scene, five minutes after the challenge existed
```

The comparison is **human-verifiable, not machine-measured**: open the frames, read
the code, see the Moon where and as predicted. A calibrated astrometric residual
(plate-solving) is named future work in the normative document, not claimed here.

## Verification

- Final bundle sha256 `32ec9b4eeb00906bc5d27ec5ddd7573ee7a25aef5ded69e8469bf9977636bcfc`
  (473,536 bytes): verdict **`SANDWICH_PASS`**, all checks true including
  `S_CAMERA_BINDING` and, with the frames present, `S_PHOTO_FILES`; burial depth 10.
- The ten original frames are in `live/g2b-work/photos/` exactly as captured
  (30.7 MB, EXIF intact); their digests are inside both the camera evidence blob and
  the bundle's top-level manifest, which must agree.
- OpenTimestamps sidecar: `vectors/valid/astro-sandwich-bundle.cbor.ots` (two public
  calendars, pending → upgradable to a Bitcoin block attestation).

## Limits, stated plainly

- The handwritten code binds the capture to B0 as *human-checkable content*; a
  determined forger could composite a photograph. The machine-checked lower bound
  covers the recorded evidence bytes, and the upper bound (block C) covers everything.
- EXIF times are the phone's own clock, labeled `OPERATOR_ASSERTED`, given ±274 s;
  the NTP witnesses in the same checkpoint carry the tight consolidation interval,
  and the sandwich carries the causal claim.
- Location is the operator-stated city (reference coordinates), not GNSS.
- Observer, miner, and laboratory operator are the same person; implementation
  diversity is real, operator diversity is not — same disclosure as every round.
