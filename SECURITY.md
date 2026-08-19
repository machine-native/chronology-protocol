# Security and Cryptographic Succession

Production Profile PQ-5 deliberately uses two signature families with different underlying
constructions:

- ML-DSA-87 (module-lattice)
- SLH-DSA-SHAKE-256s (stateless hash-based)

It also uses:
- SHA-256
- SHAKE256 with a 384-bit output

No algorithm is treated as eternal.

## Succession rule

When a suite is deprecated, historical objects remain byte-for-byte unchanged. A new `Renewal`
object commits to the entire prior evidentiary lineage and adds successor-suite signatures and
anchors.

Security therefore rests on timely renewal plus preserved evidence, not on a promise that today's
algorithm is mathematically immortal.

## Key handling

Milestone 1 generates disposable test keys.

A production deployment should:
- keep private keys in a hardware-backed boundary where practical;
- publish key manifests;
- separate witness identity from keys;
- record activation/revocation epochs;
- support overlapping old/new signatures during rotation;
- preserve historical public keys and signatures forever.
