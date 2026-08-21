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

## Claims added after the v0.2–v0.4 gates (each earned by a shipped, verified artifact)

- Acquired evidence bytes came into existence **after** a named anchor block, because a
  value derived from that block's hash by a preimage-resistant function is embedded in,
  and returned by, the remote exchange (`B0 ≺ acquisition`).
- The same evidence existed **before** a named anchor block's proof-of-work was found,
  because that block's coinbase commits to it through the checkpoint chain
  (`acquisition ≺ C`), and revising it costs the burial work of `B1…`.
- Real (non-simulated) source evidence is preserved bit-exactly and every claimed
  measurement re-derives deterministically from the recorded wire bytes.
- A Roughtime witness's response was **signed by the declared key** over a Merkle root
  containing our challenge-derived nonce, and its delegation chains to a pinned
  long-term key within its stated validity window.
- A named set of photographic frames existed inside the causal window, hashed exactly
  as recorded.
- A checkpoint chain links successive epochs, each committed into its own PoW block.

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

## Must not be claimed by the v0.2–v0.4 profiles specifically

- that any time source **told the truth** — the sandwich bounds *when* evidence was
  acquired, never whether its content is correct
- that an NTP witness is authenticated (it is not; `auth_state` says so)
- that a Roughtime signature implies precision — current deployments are
  one-second-granularity (±2–4 s), coarser than the unsigned NTP path
- that a long-term Roughtime key **is** a named operator: the signature chain is
  proven, the key→operator mapping is pinned metadata
- that a handwritten in-frame code is a cryptographic binding — it is
  human-verifiable content, compositable by a determined forger
- that a handheld photograph is a calibrated astrometric measurement, or that any
  prediction-vs-photograph agreement has been *measured* rather than eyeballed
- that a model expectation (ERA, ephemeris, engine output) is evidence, however
  precisely it is computed
- that EXIF timestamps establish anything beyond the camera's own assertion
- that a pending OpenTimestamps attestation is a Bitcoin confirmation
- that difficulty-1 causal bounds carry economic security margin
- that implementation diversity is operator diversity
