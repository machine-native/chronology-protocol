# Authenticated Time Witnesses — epoch 3, height 264, 2026-08-21

The first CHRN checkpoint containing **cryptographically signed** time evidence: two
Roughtime servers' Ed25519-signed responses over nonces derived from the sandwich
challenge, beside five unauthenticated NTP witnesses, all in one consensus.
Authoritative artifact: `vectors/valid/roughtime-sandwich-bundle.cbor`
(offline verifier: `scripts/verify_sandwich.py`).

## The sandwich

```
B0   00000000120059e003e8bf7e32d29866a37188aee93a976651b7ce3aa754202d   height 263
  ≺  acquisition  2026-08-21 ~06:17-06:18 UTC
       ROUGHTIME (signed, auth_state SERVER_SIGNED_ED25519):
         roughtime.cloudflare.com:2003  midp 1787293075/1787293076  RADI 1s  ±2.02s
         time.txryan.com:2002           midp 1787293081             RADI 3s  ±4.17s
       NTP (unauthenticated, finer): NIST, PTB, Google, Microsoft, Apple — 2 rounds each
       7 logical witnesses, consensus q=3 of 7, f=1
  ≺
C    0000000032580c2f20211b668bb643965dda2dff3a7621bf9797599d75de710c   height 264
       nNonce 1780533975, real difficulty-1 work, parent = B0 (adjacent-block window,
       won on the first attempt), epoch-3 checkpoint chained to the epoch-2
       (astronomical) checkpoint, which chains to epoch 1 and the sealed epoch 0
  ≺
B1…  NOT YET MINED at publication. Verdict is `SANDWICH_PASS_UNBURIED` — every
     check passes and both causal bounds hold; only burial depth is 0, because
     the laboratory's miner had not yet extended the chain (its cadence is
     irregular: recent inter-block gaps ranged 6 to 184 minutes). Burial is
     recorded by re-running `scripts/assemble_g5_bundle.py`, which re-fetches
     the chain and re-verifies; the epoch-1 and epoch-2 bundles were buried
     2 and 10 deep respectively by that same independent miner.
```

## What is cryptographically new

Under the NTP profile the lower causal bound rests on the server *echoing* a
challenge-derived nonce — strong, but unsigned and forgeable by a path attacker.
Under `ROUGHTIME/v1` the server **signs** a Merkle root that includes our nonce:

```
nonce  = SHA-512("CHRONOLOGY/SANDWICH-RT-NONCE/v1" || 0x00 || q || host || seq)[0:32]
leaf   = SHA-512(0x00 || nonce)[0:32]        node = SHA-512(0x01 || L || R)[0:32]
SIG    = Ed25519(delegated key, "RoughTime v1 response signature\0"  || SREP)
CERT   = Ed25519(long-term key, "RoughTime v1 delegation signature--\0" || DELE)
         MIDP ∈ [MINT, MAXT]
```

Every constant above was pinned empirically against live servers before being
hard-coded (see §3b of the normative document); all of it re-verifies offline from
the recorded bytes with no network and no trust in this project.

## Verification

- Bundle verdict **`SANDWICH_PASS_UNBURIED`** at publication — all checks true
  including `S_ROUGHTIME_SIGNATURES`, burial depth 0 (see above); suite 29 tests
  (2 new: synthetic Roughtime round-trip with four distinct tamper cases, and
  request-shape).
- The two signed servers agree on the midpoint within their stated radii, and the
  five NTP witnesses fall inside the same consensus interval — mixed-precision
  witness classes consolidated without changing the consensus algorithm.

## Limits, stated plainly

- **Signed but coarse.** Current Roughtime deployments serve one-second-granularity
  midpoints; the uncertainty (±2–4 s) is an order of magnitude wider than NTP's.
  The signature buys authentication, not precision — which is exactly why both
  classes ride in one checkpoint.
- **Key→operator mapping is metadata, not proof.** The long-term keys are pinned
  from a published ecosystem snapshot and travel inside the evidence blob. The
  signature chain is proven; that a given key *is* Cloudflare's is asserted by that
  snapshot's provenance, and stated as such.
- Two of the four ecosystem servers were unreachable (classic protocol dead
  everywhere; `roughtime.se` and `roughtime.int08h.com` silent on both wire
  formats) — recorded rather than quietly dropped.
- Difficulty-1 bounds remain mechanical, not economic; same disclosure as every
  round, and the same reason the OpenTimestamps sidecars exist.
