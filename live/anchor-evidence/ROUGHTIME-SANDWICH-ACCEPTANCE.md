# Authenticated Time Witnesses — epoch 3, 2026-08-21

> ## ⚠️ CORRECTION — the first anchor attempt was orphaned
>
> **`v0.4.0` published this checkpoint as anchored at height 264 in block
> `0000000032580c2f20211b668bb643965dda2dff3a7621bf9797599d75de710c`. That block
> lost a chain race and is NOT on the active chain.** The laboratory's miner
> produced a competing block at the same height
> (`00000000cda96f0eeff6d3202f446f5bb1fbcd02a46c45242a29a500419e7518`) and
> extended it to 265, so its branch won. Our block carries valid difficulty-1
> work and was briefly the tip; it is now an orphan.
>
> The statement is corrected here rather than deleted, and `v0.4.0`'s release
> note is left standing with a pointer to this correction — a claim that quietly
> disappears teaches a reader nothing.
>
> **What the reorganization did and did not touch.** The acquisition, every
> signature, and the epoch-3 checkpoint are unchanged — not one evidence byte
> depended on which block won. Only the anchor's identity changed. The sandwich
> was re-anchored by mining the *same* checkpoint payload onto the new tip:
>
> ```
> re-anchored C   000000001a5380c4c618b2fd2dc4a8768e5cd807cf3122a24ce2fc4c548dc112
>                 height 269, nNonce 796895470, real difficulty-1 work
> ```
>
> The causal window widened from adjacent (263→264) to six blocks (263→269), and
> the verifier's `S_LINKAGE_B0_TO_C` check now walks the five intervening blocks
> — the VM's winning 264 and its 265–268 — proving the unbroken path from B0 to
> the new anchor. Both bounds hold: B0 still precedes the acquisition, and C
> still commits to the same evidence. **This is the first chain reorganization
> the construction has survived, and it behaved as designed: a wider window, no
> lost evidence, and every claim re-verified rather than re-asserted.**

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
C    000000001a5380c4c618b2fd2dc4a8768e5cd807cf3122a24ce2fc4c548dc112   height 269
       nNonce 796895470, real difficulty-1 work. The first attempt at height 264 was
       orphaned (see the correction above); this is the re-anchor, so the window is
       263→269 rather than adjacent. Epoch-3 checkpoint chained to the epoch-2
       (astronomical) checkpoint, which chains to epoch 1 and the sealed epoch 0
  ≺
B1…  NOT YET MINED at publication. Verdict is `SANDWICH_PASS_UNBURIED` — every
     check passes and both causal bounds hold; burial depth is 0 because the
     re-anchor had only just been mined. Its cadence is irregular (recent gaps
     ran 6 to 184 minutes, and it produced three blocks in fifteen minutes on
     the morning of the 21st). Burial is recorded by re-running
     `scripts/assemble_g5_bundle.py`, which re-fetches the chain and
     re-verifies; the epoch-1 and epoch-2 bundles were buried 2 and 10 deep
     respectively by that same independent miner.
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
