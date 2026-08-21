# Chronology Protocol v0.1.0 — Milestone 1 Release Candidate

## Completed in this package

- normative protocol specification and immutable invariants
- protocol-genesis object binding every observation/checkpoint to exact normative-document commitments
- deterministic restricted-CBOR encoding
- integer-picosecond interval model
- exact quorum-supported interval algorithm with explicit `TIME_CONFLICT`
- explicit `ORDER_INDETERMINATE`
- logical witness chains with predecessor commitments
- independent SHA-256 and SHAKE256-384 commitments
- real ML-DSA-87 and SLH-DSA-SHAKE-256s signatures via OpenSSL 3.5+
- additive cryptographic-renewal object
- dual-hash Merkle checkpoints
- 96-byte CHRN v1 anchor payload
- 98-byte Jan09-compatible coinbase scriptSig
- exact v0.1 transaction/block serialization
- project derivative genesis reproduction test
- raw Bitcoin anchor parser/extractor
- exact median-time-past contextual rule in the live template path
- transparent native SHA-256d nonce scanner
- v0.1-era P2P block submitter
- standalone self-contained evidence-bundle verifier
- adversarial/tamper tests
- live integration procedure

## Deliberately not claimed

This release does not claim:
- universal absolute time
- perfect simultaneity
- real GNSS/atomic hardware evidence
- a live mined chronology-anchor block
- live-node acceptance
- permanent unbreakability of any current cryptographic primitive

## Status meanings

`PASS_PRE_POW`
: All evidence, cryptographic, serialization, anchor and pre-PoW checks pass. The candidate block has
  not yet satisfied or demonstrated a new live PoW/chain acceptance event.

`PASS_LIVE_ANCHORED`
: Reserved for a future evidence bundle that includes a valid mined block plus independently
  captured acceptance/active-chain evidence from the unmodified Jan09-derived network.

No script in v0.1.0 silently upgrades `PASS_PRE_POW` to `PASS_LIVE_ANCHORED`.

---

# v0.1.1 — Live anchor executed (2026-08-19)

The external gate declared above was completed on 2026-08-19. The sealed 96-byte CHRN
checkpoint payload was carried, byte-identical, in the coinbase of a really-mined
difficulty-1 block accepted as the active tip of the live laboratory chain:

```
block   00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b   height 221
chain   Bitcoin (2026), genesis 00000000ad12f3ec…   nNonce 2757362010
```

Evidence, in four independent forms — the operated seed's active chain, an independent
full-chain linkage re-verification, an unmodified released Jan09-derived client's own
acceptance log, and the bundle verifier's `PASS` verdict (all 13 checks true) — is in
[`live/anchor-evidence/ACCEPTANCE.md`](live/anchor-evidence/ACCEPTANCE.md). The
live-anchored bundle is `vectors/valid/evidence-bundle-live-anchored.cbor`; the sealed
v0.1.0 bundle and `MANIFEST.sha256` remain untouched, exactly as sealed.

Two earlier candidates with valid PoW lost their height races to the laboratory's own
miner and are disclosed in the acceptance record. `PASS_LIVE_ANCHORED` was reached by
adding mined-and-accepted reality to the sealed evidence, never by editing a verdict.

---

# v0.2.0 — The reality sandwich (2026-08-19)

First **real** (non-simulated) evidence acquisition, causally sandwiched between live
proof-of-work blocks. Normative construction: [`docs/REALITY-SANDWICH.md`](docs/REALITY-SANDWICH.md).

```
B0  = 00000000fc80fe4f…  height 221   (the v0.1.1 live-anchor block itself)
        ≺  acquisition: 10 real NTPv4 exchanges, 5 independent operators
           (NIST, PTB, Google, Microsoft, Apple), challenge nonce embedded in
           every request and echoed by every server
        ≺
C   = 0000000055cddf6e…  height 222   (epoch-1 checkpoint payload, real difficulty-1 work)
```

New in this release:

- `ctp/sandwich.py` — challenge/nonce derivation, NTP witness profile with
  deterministic measurement re-derivation from raw packets, declared-origin
  picosecond frames (SPEC §3), integer-only IAU-2000 ERA expectation
  (`EXPECTATION_NOT_EVIDENCE`), sandwich bundle format, and the offline verifier
- `scripts/run_sandwich.py` / `build_sandwich_template.py` /
  `assemble_sandwich_bundle.py` / `verify_sandwich.py`
- `tests/test_sandwich.py` — derivation vectors, measurement math, and a full
  synthetic sandwich round-trip with tamper cases (suite: 25 tests)
- `vectors/valid/reality-sandwich-bundle.cbor` — the real sandwich, offline-verifiable

The epoch-1 checkpoint chains to the sealed epoch-0 checkpoint through its record
commitment. The consensus interval from the five witnesses is ±42 ms wide; the causal
window is one block on each side — the tightest this chain can express. The sandwich
proves when the evidence was acquired, never that its content is true; every
non-claim in the normative document applies.

---

# v0.2.1 — Cross-checked expectation, corrected constant, real-Bitcoin sidecar anchors (2026-08-19)

**A cross-check did its job, and the error is stated rather than buried.** The
astrolabe-engine (an independent celestial-model implementation whose Sun/Moon
positions carry its own `reference` grade, 10″, validated against JPL Horizons and
IMCCE; cited by name, version and commit in the bundle) was run against
the sandwich's consensus instant. Its GAST disagreed with the bundle's stored ERA by
~100°: the v0.2.0 integer implementation had `ERA_A_NANO` a factor of 1000 too large
(pico-turns written as nano-turns). Corrected, the two now agree to the physics:
engine GAST 140.0929°, bundle ERA 139.7493°, difference +0.3436° = the equation of
origins. A float-reference regression test pins this forever (suite: 26).

- `vectors/valid/reality-sandwich-bundle.cbor` re-assembled with the corrected
  expectation (only the labeled `EXPECTATION_NOT_EVIDENCE` field changed; every
  signed observation, checkpoint, and block byte is identical):
  sha256 `61d409059c8ccb89…`, verdict `SANDWICH_PASS`, burial 2 at assembly.
- `live/anchor-evidence/astrolabe-expectation.json` — the engine's own prediction
  for the consensus instant (GAST, Sun, Moon, with the engine's declared grades),
  produced by consuming its public surface only. Still an expectation, never evidence.
- **External anchor sidecars**: standard OpenTimestamps proofs for all three evidence
  bundles (`vectors/valid/*.cbor.ots`, via `scripts/ots_stamp.py`), submitted to two
  independent public calendars. These add an economically real upper causal bound on
  the same bytes from the public Bitcoin chain; pending attestations become Bitcoin
  block attestations after calendar aggregation (`ots upgrade` with any standard
  client). Two of four calendars were unreachable (expired TLS certificates on their
  side) — stated, and two independent attestations were obtained.

---

# v0.3.0 — The first astronomical ChronologyProof (2026-08-21)

**Sandwich v2: a real optical observation of the sky, inside the causal bounds.** On
the evening of 2026-08-20 the operator photographed the gibbous Moon over New Delhi
with a fresh challenge code — the first 16 hex digits of q, derived from block 252's
hash five minutes earlier — handwritten on paper inside the frames. Ten original
frames (EXIF intact, sha256-manifested) became a `CAMERA-PHOTO/v1` witness beside
five fresh NTP witnesses in the epoch-2 checkpoint, chained to epochs 1 and 0, mined
into height 253 (parent = B0: an adjacent-block causal window again) and buried by
ten overnight laboratory blocks.

```
B0 252  ≺  photos 15:24 UTC (code in frame)  ≺  C 253  ≺  254…263
bundle   vectors/valid/astro-sandwich-bundle.cbor
         sha256 32ec9b4eeb00906bc5d27ec5ddd7573ee7a25aef5ded69e8469bf9977636bcfc
verdict  SANDWICH_PASS — all checks, incl. S_CAMERA_BINDING and S_PHOTO_FILES
```

The bundle carries the open-astrolabe engine's expectation for the capture instant —
Moon at SW 216.6°, altitude 24.0°, 55.2% illuminated, `reference` grade — as
`prediction_json`, labeled `EXPECTATION_NOT_EVIDENCE`. The frames show exactly that.
The prediction-vs-photo comparison is human-verifiable by design in this profile;
a plate-solved astrometric residual is named future work, not claimed. Full record:
[`live/anchor-evidence/ASTRO-SANDWICH-ACCEPTANCE.md`](live/anchor-evidence/ASTRO-SANDWICH-ACCEPTANCE.md);
normative profile: `docs/REALITY-SANDWICH.md` §6. Suite: 27 tests.

---

# v0.4.0 — Authenticated time witnesses (2026-08-21)

**The lower causal bound becomes cryptographic.** Under the NTP profile a server
*echoes* the challenge-derived nonce; under the new `ROUGHTIME/v1` profile the server
**Ed25519-signs** a Merkle root containing it. Epoch 3 puts both classes in one
checkpoint: two signed Roughtime witnesses (Cloudflare, txryan) beside the five NTP
witnesses, consensus q=3 of 7, anchored at height 264 with parent = B0 — the fourth
consecutive adjacent-block causal window, won on the first attempt.

```
B0 263  ≺  signed acquisition 06:17 UTC  ≺  C 264 (epoch 3)
bundle   vectors/valid/roughtime-sandwich-bundle.cbor
verdict  SANDWICH_PASS_UNBURIED — all checks incl. S_ROUGHTIME_SIGNATURES;
         burial depth 0 at publication (the laboratory miner had not yet
         extended the chain; its gaps run 6-184 min). Re-running
         scripts/assemble_g5_bundle.py records burial when it lands.
```

New in this release:

- `ctp/roughtime.py` — IETF-draft Roughtime client and complete offline verifier:
  challenge-derived nonce, Merkle inclusion, response signature, delegation
  signature against pinned long-term keys, delegation-window containment. Ed25519
  through the OpenSSL CLI, so no new Python dependencies. Every wire constant was
  pinned empirically against live servers before being hard-coded.
- `scripts/run_g5.py`, `scripts/assemble_g5_bundle.py`, `tests/test_roughtime.py`
  (synthetic round-trip with four tamper cases). Suite: 29 tests.
- `scripts/ots_upgrade.py` (from v0.3.1) and the normative profile in
  `docs/REALITY-SANDWICH.md` §3b, including the honest precision trade: signed
  evidence is currently ±2–4 s against NTP's ±30–200 ms.

Record: [`live/anchor-evidence/ROUGHTIME-SANDWICH-ACCEPTANCE.md`](live/anchor-evidence/ROUGHTIME-SANDWICH-ACCEPTANCE.md).
The epoch chain now reads 0 → 1 → 2 → 3, every link committed into proof-of-work.
