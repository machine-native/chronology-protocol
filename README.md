# Chronology Protocol v0.1.0

A ledger-independent protocol for producing an append-only, cryptographically renewable
chronology of physical-time observations and anchoring compact checkpoint commitments into
January-2009-compatible Bitcoin blocks without making Bitcoin an authority over physical time.

## Scope of v0.1.0

Milestone 1 is deterministic and hardware-independent:

1. Generate simulated independent physical-time witnesses.
2. Preserve each witness's interval and raw source-evidence commitments.
3. Sign observations with two independent NIST post-quantum signature families.
4. Derive a conservative quorum-supported consensus interval or `TIME_CONFLICT`.
5. Merkle-aggregate the signed evidence.
6. Sign the checkpoint with ML-DSA-87 and SLH-DSA-SHAKE-256s.
7. Encode a 96-byte checkpoint commitment.
8. Push it into a January-2009-valid 98-byte coinbase `scriptSig`.
9. Construct an exact v0.1-format transaction/block template.
10. Verify the complete evidence chain offline.

Bitcoin consensus code is not modified.

## Fast start

Requires Python 3.10+ and OpenSSL 3.5+ with ML-DSA and SLH-DSA.

```bash
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
`59 passed`, `PASS_PRE_POW`, `PASS`, three × `SANDWICH_PASS` including the photograph
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
walks from `git clone` to a verdict on all four anchored epochs, then out to the public
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

## Licensing status

Apache License 2.0, granted at v0.1.1 for public distribution. Copyright (c) 2026 Parth Mauria
Saxena. See `LICENSE` and `LICENSING.md`.
