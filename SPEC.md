# Chronology Protocol — Normative Specification v0.1.0

Status: experimental protocol specification.

## 1. Objective

The protocol preserves an append-only, independently witnessed chronology of physical-time
observations. It does not define metaphysical or universal absolute time. It makes claims of the
form:

- an observation was represented by these canonical bytes;
- the witness attested to those bytes under the declared cryptographic suites;
- the observation's physical-time estimate lies inside an explicit interval;
- a declared quorum supports a derived interval, or no such interval exists;
- the exact checkpoint commitment was externally published by a specified anchor.

## 2. Protocol second

The protocol duration unit `tau_s` is permanently fixed for v1 as the duration corresponding to
9,192,631,770 periods of the radiation associated with the transition between the two hyperfine
levels of the unperturbed ground state of cesium-133, matching the SI-second definition at protocol
genesis.

A future metrological redefinition MUST NOT rewrite v1 elapsed durations. New metrological mappings
are additive metadata.

## 3. Integer-only metrology

Canonical protocol objects MUST NOT contain floating-point numbers.

v1 represents elapsed durations and interval endpoints in signed integer picoseconds (`ps`) relative
to a declared chronology genesis. Physical-source conversion layers are responsible for preserving
their own raw measurements and uncertainty.

## 4. Calendars

Gregorian dates, UTC labels, GPS week/time-of-week, leap-second tables, local civil time and fiscal
calendars MUST NOT determine consensus. They MAY be recorded as source metadata/evidence and MAY be
rendered as projections over the underlying chronology.

## 5. Canonical encoding

Normative bytes use the deterministic CBOR subset implemented by `ctp/cbor.py`.

Allowed types:
- signed integers
- byte strings
- UTF-8 text strings
- arrays
- maps
- booleans
- null

Indefinite lengths, floating point, tags and duplicate map keys are forbidden.

Map keys are ordered by the length of their deterministic CBOR encoding and then lexicographically
by those encoded bytes.

## 6. Domain-separated digests

Every cryptographic digest MUST include a protocol domain separator.

v1 digest pair:

- `SHA-256(domain || 0x00 || message)` -> 32 bytes
- `SHAKE256(domain || 0x00 || message, 48)` -> 48 bytes

The pair is retained so the chronology never depends on a single hash family.

## 7. Observation

An unsigned observation contains at minimum:

- protocol version
- logical witness identifier
- protocol genesis identifier
- sequence number
- previous observation digest pair, or null for sequence zero
- local monotonic counter in picoseconds
- physical-time interval `[lower_ps, upper_ps]`
- reference-frame identifier
- source observations
- hardware-state digest pair
- firmware-state digest pair

Each source observation contains:

- source type
- claimed time in picoseconds
- uncertainty in picoseconds
- authentication state
- raw evidence digest pair

The lower bound MUST be <= upper bound.

Sequence numbers MUST increase by exactly one per witness.

The previous digest pair MUST equal the unsigned-object digest pair of the preceding observation.

## 8. Observation signatures

Production Profile PQ-5 requires both:

- ML-DSA-87
- SLH-DSA-SHAKE-256s

The signature message is:

`domain("OBSERVATION-SIGN/v1") || 0x00 || canonical_cbor(unsigned_observation)`

A witness identifier is logically distinct from any individual key and SHOULD be derived from a
key-manifest object rather than a single public key.

## 9. Observation identities

Two identities are intentionally distinct:

`lineage_id`:
    digest pair of the unsigned observation.

`record_commitment`:
    digest pair of the complete signed observation record.

The first persists as the logical evidentiary observation. The second commits to the actual
signature evidence used at that point in history.

## 10. Quorum-supported interval

Given witness intervals `I_i = [L_i, U_i]`, configured Byzantine tolerance `f`, and `N >= 3f+1`,
the v1 quorum is:

`q = 2f + 1`

Define support:

`S(t) = number of witness intervals containing t`.

The accepted set is:

`C = { t | S(t) >= q }`.

For closed one-dimensional intervals this set may be computed by endpoint sweep.

If C is empty, the epoch verdict is `TIME_CONFLICT`.

If C is non-empty, the checkpoint records the minimal lower and maximal upper points of each
contiguous quorum-supported component. v0.1 requires exactly one component for `CONSENSUS`; multiple
components are `TIME_CONFLICT` rather than silently choosing one.

## 11. Event ordering

For accepted event intervals A and B:

- if `A.upper < B.lower`, then `A BEFORE B`;
- if `B.upper < A.lower`, then `B BEFORE A`;
- otherwise `ORDER_INDETERMINATE`.

## 12. Checkpoint

A checkpoint contains:

- version
- protocol genesis identifier
- epoch number
- previous checkpoint lineage digest pair, or null
- sorted signed-observation record commitments
- Merkle roots for both hash suites
- witness count
- Byzantine tolerance `f`
- quorum `q`
- consensus verdict
- consensus interval when present
- creation-policy identifier

The checkpoint is dual-signed using Production Profile PQ-5.

## 13. Merkle construction

Leaves:
`H(domain("MERKLE-LEAF/v1"), canonical(record_commitment_pair))`

Nodes:
`H(domain("MERKLE-NODE/v1"), left || right)`

Odd final leaves are duplicated.

Independent trees are formed for SHA-256 and SHAKE256-384.

## 14. Jan09 Bitcoin anchor payload

The v1 Bitcoin anchor payload is exactly 96 bytes:

| offset | size | field |
|---|---:|---|
| 0 | 4 | ASCII `CHRN` |
| 4 | 1 | anchor version = 1 |
| 5 | 1 | hash suite = 1 |
| 6 | 2 | big-endian flags |
| 8 | 8 | big-endian epoch |
| 16 | 32 | SHA-256 checkpoint record commitment |
| 48 | 48 | SHAKE256-384 checkpoint record commitment |

The 96-byte payload is encoded into the coinbase `scriptSig` as:

`OP_PUSHDATA1 0x60 <96 bytes>`

Total scriptSig size: 98 bytes.

The historical January-2009 transaction rule accepts coinbase scriptSig sizes from 2 through 100
bytes. The anchor therefore fits without a Bitcoin consensus change.

## 15. Anchor semantics

Bitcoin is an external publication/order witness only.

The Jan09 contextual block rules include `nTime > pindexPrev->GetMedianTimePast()`, `nTime <= GetAdjustedTime()+2 hours` at context-free checking time, and `nBits == GetNextWorkRequired(pindexPrev)`. The adapter MUST NOT replace these with simplified modern or approximate rules.

`nTime` MUST NOT be interpreted by this protocol as physical-time evidence.

A successful anchor proves, subject to the Bitcoin proof assumptions, that the exact checkpoint
record commitment was incorporated into that PoW history.

## 16. Cryptographic renewal

Old evidence MUST NOT be rewritten.

Before an algorithm ceases to be considered trustworthy, a renewal object commits to:

- the previous lineage identifier;
- all prior record commitments;
- prior signatures/public-key manifests;
- prior anchor proofs;
- the new cryptographic-suite declaration.

The renewal is signed/hashed using the successor suites and then externally anchored.

## 17. Conformance

A conforming verifier MUST reject:

- non-canonical encodings
- floats
- unknown mandatory fields/suites
- broken witness sequence chains
- invalid signatures
- Merkle-root mismatch
- quorum arithmetic mismatch
- fabricated consensus interval
- malformed anchor payload
- Bitcoin transaction/merkle/header mismatch
- invalid PoW when a mined-block claim is made

A verifier MUST be capable of returning `TIME_CONFLICT` and `ORDER_INDETERMINATE` without treating
those scientifically honest outcomes as software failures.
