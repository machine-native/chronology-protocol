# Chronology Protocol

An append-only, cryptographically renewable record of **physical-time observations**,
whose compact checkpoints are committed into January-2009-compatible Bitcoin blocks —
without making Bitcoin an authority over physical time.

Every claim below is checkable from bytes, offline, without trusting this project.
One command gives a verdict: `python scripts/verify_all.py`.

## What has actually been done

Seven checkpoints, each committed into a real proof-of-work block, each chained to the
one before it, all offline-verifiable:

| epoch | block | what it establishes |
|---|---|---|
| 0 | 221 | the sealed package live-anchors — verdict `PASS` |
| 1 | 222 | first real acquisition, causally sandwiched between two blocks |
| 2 | 253 | a photographed Moon inside the causal bounds |
| 3 | 269 | Ed25519-**signed** time evidence — survived a reorg from height 264 |
| 4 | 322 | a rolling code proving **elapsed time**, not merely an instant |
| 5 | 479 | a record from another system given a checkable time bound |
| 6 | 530 | 115 real air measurements bound to proof-of-work |
| 7 | 628 | 958 observations from two particulate sensors and a hygrometer, buried 104 deep |

**10 proofs · 25 attestations · 17 distinct blocks**, every block confirmed against a
public explorer by `scripts/confirm_attestations.py` — which ships, so the count can be
repeated rather than taken on trust. That proof-of-work is the only part of this
evidence produced by people with no connection to this project.

It also runs on hardware. A Cmod A7-35T FPGA mined block 298 at 6.9854 MH/s, and a
306-byte block crossed 13.7 m and a cement wall by LoRa radio to a machine that had
been offline since eighteen minutes before that block existed.

## Scope

Milestone 1 (`run_milestone1.py`) is deterministic and hardware-independent: simulated
witnesses, preserved intervals, two independent post-quantum signature families, a
quorum-supported consensus interval or an explicit `TIME_CONFLICT`, Merkle aggregation,
a 96-byte checkpoint commitment, a Jan09-valid 98-byte coinbase `scriptSig`, and offline
verification of the entire evidence chain.

Everything in the table above is that same machinery driven by real observations.

Bitcoin consensus code is not modified.

## Fast start

Requires Python 3.10+ and OpenSSL 3.5+ with ML-DSA and SLH-DSA.

```bash
python scripts/verify_all.py          # every check in VERIFY.md, one verdict
python scripts/run_milestone1.py
python scripts/verify_bundle.py vectors/valid/evidence-bundle.cbor
python -m pytest -q
python scripts/release_audit.py
```

Outputs are written under `reports/` and `vectors/`.

To compile the optional native SHA-256d nonce scanner:

```bash
make miner
```

## Live-chain gate

`run_milestone1.py` deliberately does **not** pretend to have mined a new difficulty-1 block.
It emits a candidate block template and verifies all pre-PoW invariants. A live acceptance claim
requires:

1. supply the current previous block hash/time/bits,
2. perform real difficulty-1 work,
3. submit the resulting block to the running chain,
4. capture the unmodified node's acceptance evidence,
5. add that evidence to the verification bundle.

That is an execution gate, not a protocol-design gap.

**Completed 2026-08-19.** Block
`00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b` (height 221 of the
live laboratory chain, real difficulty-1 work, nNonce 2757362010) carries the sealed
96-byte checkpoint payload and was accepted by the operated seed and by an unmodified
released Jan09-derived client. See `live/anchor-evidence/ACCEPTANCE.md` and
`vectors/valid/evidence-bundle-live-anchored.cbor` (verifier verdict: `PASS`, 13/13).

## A block moved by radio, to a machine that could not already have had it (2026-09-06)

The receiver was air-gapped at 15:54:06Z and its isolation recorded rather than
asserted — `ping` failing, no adapter holding a gateway, the output directory absent.
Block 732 was mined at 16:12:05Z, **eighteen minutes after the receiver went offline**,
so it did not exist anywhere in the world when that machine lost its connection. It
cannot have been pre-staged, cached or synced.

Its 306 bytes became three CHRB fragments, sent over three passes at 866 MHz across
13.7 m, a thick cement wall, a wooden door and a cupboard. All nine transmissions
arrived and the set completed on the first pass. RSSI −52 to −61 dBm, SNR 8–9 dB.

The receiver validated the proof-of-work locally, still offline, trusting the sender
for nothing. Only then was it reconnected, and it queried the chain itself: tip 732,
hash identical. The received file's SHA-256 matches on both machines
(`dd35739a…`). Records: [`live/lora-experiment/`](live/lora-experiment/).

## Air measurements bound to proof-of-work (epochs 6 and 7)

Epoch 6 committed 115 real air measurements. Epoch 7 committed 958 observations from
two PMS7003 particulate sensors and a BME280, verdict `SANDWICH_PASS`, now buried 104
blocks deep. The bridge forwards raw sensor frames and raw ADC counts and interprets
nothing, so every value stays recomputable by a reader who distrusts the arithmetic.

## A record from another system, given a time bound (epoch 5)

[`docs/EXTERNAL-BINDING.md`](docs/EXTERNAL-BINDING.md) specifies how a record produced
elsewhere obtains a checkable time bound — the binding tag must travel *into* the other
system, not merely be asserted about it. Performed twice: a SATROOT namespace at epoch
5, and the air batch at epoch 6.

Building the second exposed that `verify_sandwich` did not recognise its own new
evidence type, so both bindings initially failed their own verifier. That is recorded
here rather than quietly fixed.

## Mined by purpose-built hardware (block 298)

A Cmod A7-35T running a SHA-256d miner written for this project mined block 298 on
2026-08-23 — the first block on this chain from purpose-built hardware. 0.0906 →
6.9854 MH/s across six measured configurations, each landing within 1.4% of its
projection. Four separate claims — simulated, synthesised, ran on a board, mined a
block — each first made on the day it became true, and not before.

## Authenticated time witnesses (v0.4.0)

Epoch 3 (height 269, after its first anchor at 264 was orphaned in the chain's first
reorganization — see v0.4.1) carries **server-signed** time evidence: two Roughtime servers
Ed25519-sign a Merkle root containing a nonce derived from the sandwich challenge, so
the lower causal bound is cryptographic rather than merely echoed. They ride beside
the five NTP witnesses in one consensus (q=3 of 7) — signed-but-coarse (±2–4 s) and
unsigned-but-fine (±30–200 ms) consolidated without changing the consensus rule.
`ctp/roughtime.py` verifies the whole chain offline; profile and precision trade in
`docs/REALITY-SANDWICH.md` §3b.

## The first astronomical ChronologyProof (v0.3.0)

On 2026-08-20 a real observation of the Moon over New Delhi — ten photographs with a
challenge code derived from block 252's hash handwritten inside the frames — was
checkpointed beside five NTP witnesses and mined into height 253, an adjacent-block
causal window, buried by ten laboratory blocks overnight. The bundle carries the
open-astrolabe engine's prediction (SW 216.6°, alt 24.0°, 55% lit — which is what the
frames show) as a labeled expectation. `vectors/valid/astro-sandwich-bundle.cbor`,
verdict `SANDWICH_PASS`; record in `live/anchor-evidence/ASTRO-SANDWICH-ACCEPTANCE.md`.

## The reality sandwich (v0.2.0)

The first real acquisition: `B0 ≺ acquisition ≺ C`. Ten live NTPv4 exchanges against
five independent operators, each request carrying a nonce derived from B0's block hash
and echoed by the server, the whole evidence set committed into the epoch-1 checkpoint
mined into block C at height 222. Construction and non-claims:
[`docs/REALITY-SANDWICH.md`](docs/REALITY-SANDWICH.md); bundle:
`vectors/valid/reality-sandwich-bundle.cbor`; verifier: `scripts/verify_sandwich.py`
(offline, network-free).

## ⭐ Wanted: one independent verifier

Everything here is checkable from bytes. The one thing missing cannot be produced by
writing more code: **nobody outside the project has verified it and said so publicly.**
Ten minutes, entirely offline, no accounts, nothing of ours running on your machine —
[**CALL-FOR-VERIFICATION.md**](CALL-FOR-VERIFICATION.md).

Mining is equally open: every block on the anchor chain so far was mined by this
project, and the next accepted block belongs to whoever finds it.

## Independently verified

**2026-08-22 — [issue #1](https://github.com/machine-native/chronology-protocol/issues/1).**
A party outside this project cloned the repository themselves at commit `fc5933d`, ran
the full offline verifier, and published the result from their own GitHub account:
102 tests with zero failures (some skip when optional evidence files are absent),
`PASS_PRE_POW`, `PASS`, three × `SANDWICH_PASS` including the photograph
digests, and every OpenTimestamps digest matching. They also confirmed one Bitcoin
attestation directly against a public block explorer — a comparison no code of ours
takes part in.

They stated their limits precisely: no mining attempted, the live-chain step not run,
one of five attestations independently checked, and the post-quantum verification run
in a container because Ubuntu 24.04 LTS ships an OpenSSL too old for it.

Scope, full result, and what a reader can and cannot check for themselves:
[`live/anchor-evidence/VERIFICATION-CLAIMS-RECEIVED.md`](live/anchor-evidence/VERIFICATION-CLAIMS-RECEIVED.md).
An earlier claim was recorded and then **withdrawn** for lacking exactly this
provenance; that history is kept at
[`INDEPENDENT-VERIFICATION-01.md`](live/anchor-evidence/INDEPENDENT-VERIFICATION-01.md).

**More verifiers still wanted** — one report is a start, not a consensus. And mining
remains open: every block on the anchor chain was mined by this project, so the next
accepted block belongs to whoever finds it.

## Verify this yourself

Everything here is checkable from bytes, by you, without trusting us: **[VERIFY.md](VERIFY.md)**
walks from `git clone` to a verdict on all seven anchored epochs, then out to the public
Bitcoin blocks that attest them. It states the one hard dependency (OpenSSL 3.5+) up
front and names the platform where the official OpenTimestamps client is currently
broken, rather than letting you discover either the hard way.

## Scientific claim

This protocol does **not** claim universal absolute time or exact simultaneity across spacetime.
It records physical-time observations as explicit intervals with uncertainty and preserves their
cryptographic and causal lineage. Calendars and civil timescales are projections, not consensus.

## Security philosophy

- no authoritative clock
- no calendar in consensus
- no silent correction
- no exactness without uncertainty
- no single physical source
- no single witness
- no single cryptographic primitive
- no single blockchain
- no destructive migration
- deterministic offline verification

## Release history

Seven releases, each tied to evidence that existed when it shipped:
[`RELEASE_NOTES.md`](RELEASE_NOTES.md).

## Licensing status

Apache License 2.0, granted at v0.1.1 for public distribution. Copyright (c) 2026 Parth Mauria
Saxena. See `LICENSE` and `LICENSING.md`.
