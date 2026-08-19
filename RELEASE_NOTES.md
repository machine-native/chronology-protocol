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
