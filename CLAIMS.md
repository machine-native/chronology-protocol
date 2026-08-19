# Claims Register

## Claims v0.1 may make after the relevant gate passes

- Canonical object bytes reproduce deterministically.
- Observation hash chains are internally consistent.
- Declared PQ signatures verify under the declared public keys.
- A quorum-supported interval was derived exactly by the specified rule.
- A checkpoint commits to the included signed evidence.
- A 96-byte checkpoint commitment maps to a 98-byte Jan09-compatible coinbase scriptSig.
- The Bitcoin serializer reproduces the project's known 2026 genesis block exactly.
- A candidate Bitcoin block's transaction, Merkle root and header are internally consistent.
- A mined block meets the declared compact target.
- An exact checkpoint was incorporated into a specific PoW block, once node/chain evidence exists.

## Claims v0.1 must not make

- universal absolute time
- perfect simultaneity across spacetime
- zero uncertainty
- GPS/Galileo are immutable
- authenticated navigation data implies unspoofable ranging
- Bitcoin `nTime` is physical time
- proof-of-work gives an exact wall clock
- any cryptographic algorithm is permanently unbreakable
- “quantum proof forever”
- a simulated witness establishes a real physical measurement
- live-chain acceptance before the unmodified node actually accepts the mined block
