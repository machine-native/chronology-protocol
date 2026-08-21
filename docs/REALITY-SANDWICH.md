# The Reality Sandwich — CHRN sandwich v1 (normative)

Causal shape:

```
B0   ≺   acquisition   ≺   C   [≺ B1 ≺ B2 ...]
```

A reality sandwich proves that a body of acquired evidence came into existence inside a
bounded causal window on a proof-of-work chain. It never proves the evidence's *content*
is true — only *when* it was acquired, to within the window, without trusting the
acquiring party's clock or honesty about ordering.

## 1. Definitions

- **Anchor chain** — a January-2009-compatible proof-of-work chain. For this
  implementation: the laboratory chain with genesis `00000000ad12f3ec…`.
- **B0** — an anchor-chain block chosen at acquisition start (normally the current tip).
  Its hash seeds the freshness challenge.
- **session-id** — 32 random bytes chosen by the acquiring party, making concurrent
  sandwiches over the same B0 distinct.
- **Challenge** —
  `q = SHA-256("CHRONOLOGY/SANDWICH-CHALLENGE/v1" || 0x00 || bytes(hash(B0)) || session-id)`.
- **Exchange nonce** — for source host `h` and witness sequence `n`:
  `SHA-256("CHRONOLOGY/SANDWICH-NONCE/v1" || 0x00 || q || h || byte(n))[0:8]`.
- **Acquisition** — one or more wire exchanges with external evidence sources in which
  the exchange nonce is embedded in the *request* such that the *response* provably
  depends on it (for NTPv4: the client transmit timestamp, echoed verbatim by the server
  in the originate field of the signed-off response).
- **C** — the anchor block whose CHRN payload (epoch ≥ 1) commits, through
  checkpoint → Merkle root → observation records → source-evidence digest pairs, to the
  exact acquired evidence bytes.
- **B1…** — anchor blocks extending C (burial).

## 2. The two causal bounds

**Lower bound (B0 ≺ acquisition).** Each recorded response contains a value derived by a
preimage-resistant hash from `hash(B0)`. Absent a hash break, the response bytes could
not have been produced before B0's hash existed. The bound covers the *evidence bytes*,
not merely a claim about them.

**Upper bound (acquisition ≺ C).** C's coinbase payload commits to the evidence bytes
through the checkpoint commitment chain. Finding C's proof-of-work after choosing the
payload means the evidence existed before C's hash did. Burial by B1… makes revising C
progressively more expensive in re-done work.

The window's *physical* width is bounded by the anchor chain's block cadence, not by
anyone's clock. Nothing inside the window is ordered by this construction; the
observations' own intervals (with stated uncertainty) carry the finer claim, and remain
exactly as trustworthy as their sources — no more.

## 3. NTP witness profile (this implementation)

- Sources: independent NTPv4 servers over UDP, `auth_state = "UNAUTHENTICATED"` —
  plain NTP is spoofable in transit; diversity of operators and paths is the mitigation,
  and the profile states this rather than hiding it. Leap-smearing operators (e.g.
  Google) serve a smeared UTC near leap seconds; no leap event was active at acquisition.
- Two chained observations (sequences 0 and 1) per logical witness; witness id =
  `H(DOM_WITNESS || "NTP:" + host)`.
- Measurement derivation is deterministic from recorded packets:
  `claimed = t3 + path/2`, `path = rtt_monotonic − (t3 − t2)`,
  `uncertainty = path/2 + root_dispersion + root_delay/2 + 2 ms local margin`.
  No local wall-clock value enters the claim; the local monotonic clock only measures
  the round trip.
- Interval endpoints are integer picoseconds relative to a **declared frame origin**
  (SPEC §3) carried in the frame string: `UTC-PS-ORIGIN-<unix-seconds>/v1`.
- The epoch-1 checkpoint chains to the sealed epoch-0 checkpoint via its record
  commitment (`previous`), and is signed ML-DSA-87 + SLH-DSA-SHAKE-256s as always.

## 3b. Roughtime witness profile (ROUGHTIME/v1) — authenticated time evidence

The signed upgrade of the NTP profile, over the IETF Roughtime wire (draft-11 framing,
confirmed against roughtime.cloudflare.com and time.txryan.com, 2026-08-21):

- The 32-byte request nonce is derived from the challenge:
  `SHA-512("CHRONOLOGY/SANDWICH-RT-NONCE/v1" || 0x00 || q || host || seq)[0:32]`.
  The server's Ed25519-signed response covers a Merkle tree that includes this nonce —
  **the lower causal bound is server-signed**, not merely echoed.
- Offline verification re-derives everything from the recorded bytes: Merkle inclusion
  (`SHA-512(0x00||nonce)[:32]` leaves, `SHA-512(0x01||L||R)[:32]` nodes), the response
  signature (`"RoughTime v1 response signature\0"` context, delegated key), the
  delegation (`"RoughTime v1 delegation signature--\0"` context, long-term key), and
  the midpoint's containment in the delegation window. Ed25519 via the OpenSSL CLI —
  no new dependencies.
- `auth_state = "SERVER_SIGNED_ED25519"`. Long-term keys ride in the evidence blob;
  the key→operator mapping comes from a pinned ecosystem snapshot (provenance stated
  in the blob's profile doc) — the signature chain is proven, the operator identity
  behind a key is metadata.
- Precision trade, stated: current servers serve one-second-granularity midpoints
  (uncertainty ±2–4 s vs NTP's ±30–200 ms). Signed-but-coarse beside
  unsigned-but-fine is exactly why both witness classes sit in one checkpoint.

## 4. Bundle and verification

`SandwichBundle` (deterministic restricted CBOR): version, B0 raw block + height,
session-id, evidence blobs (raw request/response bytes and local monotonic timestamps),
signed observation history, signed checkpoint, block C raw, connecting headers
(B0 → C, exclusive), burial headers, ERA expectation, protocol genesis.

`verify_sandwich` re-derives everything offline: B0 PoW; challenge and per-exchange
nonces; nonce presence in each request and echo in each response; evidence-digest
binding into the signed observations; deterministic re-derivation of every claimed
measurement from raw packets; the full v0.1.0 bundle checks (PQ signatures, witness
chains, consensus rule, Merkle root, payload-in-coinbase, C PoW); header linkage
B0 → C; burial-chain validity. Verdicts: `SANDWICH_PASS` (buried ≥ 1),
`SANDWICH_PASS_UNBURIED`, `FAIL`.

## 5. The expectation field (not evidence)

The bundle carries the Earth Rotation Angle computed from the consensus midpoint by the
IAU 2000 formula (`ERA(Tu) = 2π(0.7790572732640 + 1.00273781191135448·Tu)`, integer
nano-turns, |UT1−UTC| ≤ 0.9 s folded into the stated uncertainty). It is labeled
`EXPECTATION_NOT_EVIDENCE` and the verifier recomputes it rather than trusting it.
It exists so a future astronomical witness (a model-driven optical
observation) has a deterministic prediction to be compared against **inside the same
sandwich**. Model output never becomes evidence by being written down; only an
observation can meet it.

## 6. Optical witness profile — sandwich v2 (CAMERA-PHOTO/v1)

Version 2 adds a photographic witness alongside the NTP profile, for observations of
the physical sky:

- Before capture, the acquiring party derives the challenge q from a fresh B0 and
  **handwrites a code prefix of q inside the photographed scene**. This binding is
  *human-verifiable content* — anyone can open the frames and read the code — and is
  deliberately outside machine verification: a determined forger could composite it,
  and the profile says so. The machine-checked binding is the recorded one (q, B0,
  session inside the evidence blob committed to by block C).
- The evidence blob carries the sha256 of every original frame, per-frame EXIF capture
  times (self-asserted by the camera clock, labeled so), camera model, and stated
  location. Bundle v2 duplicates the frame manifest at top level (`photo_manifest`)
  and the verifier requires the two to match; with `--photos DIR` it also re-hashes
  the actual files.
- The camera observation's interval spans the capture session plus an honest handheld
  clock margin; its `auth_state` is `OPERATOR_ASSERTED`. The tight time backbone
  comes from the NTP witnesses in the same checkpoint; the causal bounds come from
  the sandwich, not from EXIF.
- **Rolling in-frame challenge (prepared upgrade).** The next optical run replaces
  the handwritten code with a phone screen running `tools/rolling-code.html`: a
  code that changes every slot, `code(slot) = SHA-256("CHRN-ROLL/v1:" + SEED16 +
  ":" + slot)[:12 hex]` with `slot = floor(unix_time / slot_seconds)`. Frames taken
  across two or more slots must then show a *sequence* of codes consistent with
  their EXIF timeline — far harder to composite than one static string. The
  display and the verifier aid (`scripts/rolling_code.py`) are pinned to identical
  test vectors. Reading a code off a frame remains a human step, stated as before.
- Bundle v2 carries a **prediction attachment** (`prediction_json`): the
  open-astrolabe engine's deterministic expectation for the observed body at the
  capture instant and stated location (azimuth/altitude, phase, engine grades).
  Labeled `EXPECTATION_NOT_EVIDENCE`, exactly like the ERA field. In this first
  optical profile the prediction-vs-photo comparison (position in frame, phase) is
  **human-verifiable, not machine-measured** — a calibrated astrometric residual
  (plate-solving) is named future work, not claimed.

## 7. Non-claims

- No claim that any NTP server told the truth — only that its answers were acquired
  inside the window and are preserved bit-exactly.
- No ordering claim finer than the window plus the sources' own stated intervals.
- No security-margin claim: on a difficulty-1 chain the bounds are mechanical, not
  economic. The construction is chain-agnostic; its strength scales with the anchor
  chain's work.
- The expectation field is a model output, never evidence (§5).
