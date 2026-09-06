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

> ⚠️ **Superseded by v0.4.1: the height-264 anchor above was orphaned.** The block
> was real and briefly the tip, but lost a chain race. The claim is left standing
> here with this pointer rather than edited away; the corrected anchor and the full
> account are in v0.4.1 below and in
> [`live/anchor-evidence/ROUGHTIME-SANDWICH-ACCEPTANCE.md`](live/anchor-evidence/ROUGHTIME-SANDWICH-ACCEPTANCE.md).

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

---

# v0.4.1 — The first chain reorganization, survived (2026-08-21)

**The height-264 anchor published in v0.4.0 was orphaned.** It carried valid
difficulty-1 work and the public seed advertised it as its tip, but the laboratory's
miner produced a competing block at the same height and extended it — two blocks beat
one, and our block left the active chain. This is the anchor chain's first
reorganization, and the direct consequence of it having had two independent miners
since 2026-08-19.

```
orphaned   0000000032580c2f…  height 264   valid PoW, briefly the tip, now an orphan
re-anchor  000000001a5380c4c618b2fd2dc4a8768e5cd807cf3122a24ce2fc4c548dc112
           height 269, nNonce 796895470
window     B0 263  ≺  acquisition  ≺  C 269      (six blocks, not adjacent)
verdict    SANDWICH_PASS — all checks true, buried 3 deep
bundle     vectors/valid/roughtime-sandwich-bundle.cbor
           sha256 bf22c1586a2dff27…
```

**Nothing in the evidence depended on which block won.** The acquisition, every
Ed25519 and post-quantum signature, and the epoch-3 checkpoint are byte-identical to
what v0.4.0 published; only the anchor's identity changed. Re-anchoring meant mining
the *same* checkpoint payload onto the new tip, which widened the causal window and
left both bounds intact — and the verifier proves it rather than asserting it:
`S_LINKAGE_B0_TO_C` now walks the five intervening blocks (the winning 264 and its
265–268) to establish the unbroken path from B0 to the new anchor.

**This is the construction's first encounter with a chain reorganization, and it
behaved as designed**: a wider window, no lost evidence, every claim re-verified. The
orphaned block's bytes are preserved in `live/anchor-evidence/orphans/` and the v0.4.0
release note above is left standing with a pointer to the correction — a claim that
quietly disappears teaches a reader nothing.

The laboratory's own record of the event, written from the chain bytes rather than from
this project's perspective, is in the original-bitcoin-laboratory genesis repository
under `bitcoin-findings/2026-08-21-first-reorganization/`.

# v0.5.0 — Four more epochs, a block moved by radio, and one command to check it all (2026-09-07)

The largest release since the protocol went public, and the first in which most of the
evidence comes from physical instruments rather than from the protocol exercising
itself.

## Four new anchors

```
epoch 4   height 322   a rolling code proving ELAPSED TIME, not merely an instant
epoch 5   height 479   a record from another system given a checkable time bound
epoch 6   height 530   115 real air measurements bound to proof-of-work
epoch 7   height 628   958 observations, SANDWICH_PASS, buried 104 blocks deep
```

**Epoch 4** is the first upgrade to the camera witness since epoch 2. A handwritten
challenge proves photographs came *after* B0 and nothing more — one code is one
instant. A code changing every ten seconds, captured across 19 distinct slots, also
proves the frames span real elapsed time. 41 frames, 29 carrying codes.

**Epochs 5 and 6** exercise `docs/EXTERNAL-BINDING.md`: a record produced elsewhere
obtains a time bound only if the binding tag travels *into* the other system. Building
the second binding exposed that `verify_sandwich` did not recognise its own new
evidence type, so both bindings initially failed their own verifier. Recorded here
rather than quietly repaired.

**Epoch 7** carries two PMS7003 particulate sensors and a BME280. The bridge forwards
raw frames and raw ADC counts and interprets nothing, so every published value stays
recomputable by a reader who distrusts the arithmetic.

## Experiment 1 — a block crossed a room by radio, and could not have arrived any other way

The weak form of this experiment is "a file moved between two machines with radios
attached", to which the honest objection is: how do you know it did not go over the
network, or was already there? The design makes that objection **physically
impossible** rather than answering it.

```
15:54:06Z   receiver air-gapped; isolation RECORDED, not asserted
16:12:05Z   block 732 mined -- EIGHTEEN MINUTES LATER
16:14:59Z   transmitted: 306 bytes, 3 CHRB fragments, 3 passes, 9 sends, 0 lost
            13.7 m, a cement wall, a wooden door, a cupboard
            RSSI -52..-61 dBm, SNR 8-9 dB, complete on the first pass
16:21:06Z   receiver validates proof-of-work LOCALLY, still offline
16:23:17Z   reconnected; receiver queries the chain ITSELF: tip 732, hash identical
```

The block did not exist anywhere when the receiver lost its connection, so it cannot
have been pre-staged, cached or synced. The received file's SHA-256 matches on both
machines. `RADIO-RELAY.md` no longer says the driver is untested on hardware.

Records: `live/lora-experiment/` (nine JSON evidence files).

## One command, three outcomes

`scripts/verify_all.py` runs every check in VERIFY.md and prints a single verdict:
toolchain, test suite, two plain bundles, seven sandwich bundles, and attestation
confirmation. **12 checks, all PASS.**

Three outcomes, never two — `PASS`, `FAIL`, `INDETERMINATE`, exit 0/1/2 — and the third
is exercised rather than assumed: `--skip-network` reports 11 passed, 0 failed, 1 could
not be checked, and says plainly that nothing failing is not the same as success.

That distinction is not decoration. Outside review found this project's verifier
reporting `FAIL` where it should have said `INDETERMINATE_TOOLCHAIN` — implying the
evidence was bad when only the toolchain was too old. It was the most serious defect
outside review has found, and it is not being reintroduced in the tool built to
summarise everything.

## Attestations, and an omission that was invisible by construction

`scripts/confirm_attestations.py` checks every `.ots` against a public block explorer.
**21 attestations across 13 distinct blocks, all confirmed.** The script ships, so the
count can be repeated rather than trusted.

Writing it found that the upgraded proofs had never been committed: the public
repository advertised **fifteen** attestations while holding **twenty-one**. Upgrades
only ever add evidence, which is exactly why the omission produced no symptom. A count
that can only be too low is still a count nobody can check.

## Independent verification — closed, on the second attempt, under a stricter bar

A verification report was received, recorded, and **withdrawn within hours** when a
party in a position to be the verifier denied producing it. The failure was not that
the report was false; it was that its provenance was never established. Hashing a file
supplied by one party against a number supplied by the same party is circular.

The bar is now: the artifact identified by digest, commit and toolchain, **and** the
verifier publishing from somewhere they control. Closed 2026-08-22 by
[issue #1](https://github.com/machine-native/chronology-protocol/issues/1) — a
non-collaborator who cloned at `fc5933d`, ran the offline suite, confirmed an
attestation against a public explorer, and stated their limits precisely.

They found three real defects in two days. Two are now enforced by tests.

**One report is a start, not a consensus.** More verifiers are still wanted, and mining
remains open: every block on this chain was mined by this project, so the next accepted
block belongs to whoever finds it.

## Availability

A second seed now serves the chain from a different provider in a different
jurisdiction (`docs/D2-SECOND-SEED-RUNBOOK.md`). This buys **availability, not
independence** — both seeds are still ours, and a reader who distrusts this project
gains nothing from a second machine it also runs.

## Not claimed

This release does not claim the sensors report correct absolute mass —
`reference-comparison/pm-mass` is honestly `NOT_RUN` and needs a reference instrument.
It does not claim LoRa is a practical distribution channel: three fragments for 306
bytes, a duty-cycled band and no back-channel are what they are. It does not claim more
than one outside party has verified anything.

## The release gate could not run, and said something false while not running

`scripts/release_audit.py` is this project's own pre-release check. Preparing this
release found three things wrong with it.

It **crashed** on any machine without a C compiler. `run()` did not catch
`FileNotFoundError`, so a missing `cc` aborted the whole audit and discarded every
other step's result — no report was written at all. A gate that cannot run is not a
gate.

Once it could run, it would have called that missing compiler a **failure**. That is
the conflation this project treats as its most serious defect class: "could not check"
reported as "checked and failed" says the release is bad when nothing about it was
examined. The audit now has three outcomes and exits 0/1/2 like every other verifier
here, and prints what was not asked and why.

And its report asserted **`live_anchor_claimed: false`** with a status of
`RELEASE_CANDIDATE_PASS_PRE_POW` — both hardcoded, and both untrue since v0.1.1. Seven
epochs are anchored. The field is now read from the evidence on disk, and the version
comes from the tags rather than a constant that nobody remembered to bump.

## A guard for the front page

The README's attestation tally was written from an internal status note that had gone
stale — it said 21 attestations across 13 blocks while the proofs on disk carried 25
across 17. VERIFY.md was already protected by a test that parses the `.ots` files
themselves; the README, which is what a stranger reads first, was not. It is now.

An understatement is still a number nobody can check, and this is the second time a
stale attestation count has been found in a published document.
