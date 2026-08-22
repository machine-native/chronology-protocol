# Independent verification #1 — 2026-08-22

**The first time anyone outside this project verified anything in it.** Every
acceptance record here has ended by admitting that implementation diversity was
real and operator diversity was not. That sentence can now be narrowed.

## What was verified, and by whom

An independent party, on their own machine, in a sandboxed runtime with no network
access, running their own toolchain (Python 3.13.5, pytest 9.0.2, **OpenSSL 3.5.5**).
Nothing of ours ran on our hardware for this result.

They were given the cold-storage deposit by hand as
`chronology-protocol-verification-pack.zip`, together with a note stating in advance
exactly what a green run would and would not establish. They accepted that scope
before running anything.

## Their result

```
verification-pack SHA-256          MATCH  53e983d9bd06c8231461490b873b5ac67198844d22bf80745fb5b478dfc810da
sha256sum -c MANIFEST.sha256       PASS   every listed file OK
python -m pytest -q                PASS   39 passed
evidence-bundle.cbor               PASS_PRE_POW
evidence-bundle-live-anchored.cbor PASS
reality-sandwich-bundle.cbor       SANDWICH_PASS
astro-sandwich-bundle.cbor         SANDWICH_PASS
roughtime-sandwich-bundle.cbor     SANDWICH_PASS
astro bundle + original photos     SANDWICH_PASS, S_PHOTO_FILES: true
```

Every bundle digest they reported matches ours byte-for-byte:

```
9fc2d7c767078d5445e0ca649e4e5e4ff909c4ebd828f6165cafa20c868c3854  evidence-bundle
9fbccb5b37e5c3798f557d9de91f1d60a16b86dd817544e2967fdf729d6561a4  evidence-bundle-live-anchored
61d409059c8ccb891acd84b663ee898ff025e67178af6216843b2a0e3835be71  reality-sandwich
32ec9b4eeb00906bc5d27ec5ddd7573ee7a25aef5ded69e8469bf9977636bcfc  astro-sandwich
bf22c1586a2dff27235f3473283d50388b951ec218fc8fa9d4da8ea6b432fa9b  roughtime-sandwich
```

Full transcript preserved, sha256
`9d7b0be65cbd3d28f60c73abb240774501c6f0bff7bbdc4eb6d7613927694d09` — hash confirmed
on receipt.

## The claim this supports — and its exact limits

**Established, independently of us:** the post-quantum signatures verify; every
claimed measurement re-derives deterministically from the raw recorded packets;
the Merkle trees, consensus intervals and checkpoint chain are internally
consistent; the embedded blocks satisfy their own stated proof-of-work targets;
header linkage from challenge block to anchor block is unbroken; the deliberate
tamper cases fail as designed; and the ten photographs on disk are byte-identical
to those committed into a proof-of-work block.

**Not established, and not claimed:**

- that the hand-delivered pack is byte-identical to the public repository — they
  received it from the author, and said so;
- that the anchor chain is live or accepted by anyone else — their sandbox blocked
  DNS and raw TCP entirely;
- that the Bitcoin attestations resolve — same reason;
- that any time source told the truth. The protocol bounds *when* evidence was
  acquired, never whether its content is correct.

The verifier's own label, which this project adopts verbatim:

> **Independent cryptographic verification of a hand-delivered artifact: PASS.**

## They declined to overstate — twice

On a first attempt, before receiving the pack, their sandbox blocked the clone.
They reported that they *could not* run the verifier and explicitly refused to
report the repository's expected outputs as if they were their own results. On
mining, they read `live/race.sh`, confirmed that success is only declared when the
submitted block becomes the **active tip** of a refetched chain, and declined to
claim a race they could not enter.

That is the standard this project asks of itself, met by someone with no stake in
it. It is the most valuable part of this record.

## Two real defects they found

Both were ours, and both are fixed.

1. **`scripts/ots_info.py` had an undeclared third-party dependency.** The deposit
   claimed no third-party Python was needed; `ots_info.py` imported the
   `opentimestamps` package and failed with `ModuleNotFoundError` in their clean
   environment. For a cold-storage archive this is worse than cosmetic — a reader
   in 2126 should not need a package index to check a Bitcoin attestation.
   **Fixed:** `ctp/ots.py` now parses the proof format directly using only the
   standard library, cross-checked against the reference library on all five
   proofs (identical digests and attestations), with a test that runs the read
   path under `python -S` so an accidental dependency fails loudly.
2. **Documentation drift:** `VERIFY.md` promised `29 passed` while the suite had
   grown. **Fixed:** the count is corrected and now framed as informational, with
   *zero failures* named as the actual result to look for.

A verification that finds nothing teaches nothing. This one paid for itself twice.

## What is still open

Operator diversity in *mining* remains zero — every block on the anchor chain was
mined by this project. The invitation stands and is unconditional: the next
accepted block belongs to whoever finds and submits it first.
