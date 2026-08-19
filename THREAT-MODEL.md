# Threat Model v0.1.0

## Protected properties

The protocol aims to make retrospective alteration of published evidence detectable and to prevent
one time authority, witness, signature algorithm, hash family or ledger from silently rewriting the
entire chronology.

## Adversaries considered

- malicious or compromised GNSS source
- signal spoofing, delay/rebroadcast and receiver deception
- malicious witness
- witness clock rollback
- oscillator drift/fault
- compromised firmware
- compromised signing key
- equivocation by a witness
- Byzantine minority of witnesses
- malicious checkpoint producer
- malformed/collision-oriented serialization
- signature-family cryptanalytic failure
- hash-family cryptanalytic failure
- anchor-chain reorganisation
- future quantum attacker
- archive deletion or partial evidence loss
- civil-calendar/time-scale redefinition

## Explicit non-goals

v0.1 does not:
- prove universal simultaneity
- eliminate relativity
- guarantee physical sensor honesty from software alone
- make GNSS unspoofable
- guarantee any cryptographic primitive forever
- guarantee Bitcoin survives forever
- turn miner `nTime` into a trusted clock
- infer physical time from proof-of-work rate

## Safety strategy

1. Preserve raw evidence commitments.
2. Use explicit uncertainty.
3. Record disagreement rather than normalize it away.
4. Require quorum support for consensus intervals.
5. Use two independent PQ signature families.
6. Use two independent hash constructions.
7. Maintain additive cryptographic renewal.
8. Keep anchor proofs separable and replaceable.
9. Make all verification deterministic and externally reproducible.

## Future hardware profile

Hardware additions must fit the same Observation schema:
- multi-GNSS receiver
- Galileo OSNMA evidence
- 1 PPS measurement
- disciplined oscillator
- independent atomic reference
- secure element / measured boot
- raw RF/baseband evidence where practical

Changing hardware must not redefine historical protocol objects.
