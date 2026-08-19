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

Apache License 2.0, granted at v0.1.1 for public distribution. Copyright (c) Parth
Mauria Saxena. See `LICENSE` and `LICENSING.md`.
