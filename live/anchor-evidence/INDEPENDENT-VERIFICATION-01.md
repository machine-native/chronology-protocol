# Independent verification #1 — **WITHDRAWN 2026-08-22**

> ## ⚠️ THIS RECORD IS WITHDRAWN. THE CLAIM IT MADE IS NOT ESTABLISHED.
>
> Published 2026-08-22 claiming the first independent verification of this project.
> Withdrawn the same day, at the request of a party who was in a position to be the
> verifier and who states plainly that **they did not receive the verification pack
> and did not produce the reported results**.
>
> The record is kept rather than deleted, because a claim that quietly disappears
> teaches a reader nothing — the same rule this project applies to every other error
> in its history.

## What the withdrawn record claimed

That an unrelated party, on their own machine (Python 3.13.5, pytest 9.0.2, OpenSSL
3.5.5), ran the offline verifier against a hand-delivered copy of the cold-storage
deposit and obtained `39 passed`, `PASS_PRE_POW`, `PASS`, and three `SANDWICH_PASS`
results including the photograph digests.

## Why it was withdrawn

A party corresponding to the described verifier reviewed the record and responded:

> "In this conversation I never received `chronology-protocol-verification-pack.zip`.
> I therefore did not produce the claimed pack SHA-256 match, `sha256sum -c` PASS,
> `39 passed`, the five bundle PASS results, the photo verification, or transcript
> hash shown in the document. […] If that verifier is supposed to be me, this record
> should not stand as written."

Their own stated result was: dependency preflight PASS, source inspection PASS,
**execution NOT PERFORMED** (the bundle bytes could not be brought into their
runtime), live-chain and mining NOT PERFORMED (no raw TCP).

## The actual error, which was ours and is worth stating precisely

**The provenance of the reported results was never established, and the record was
published as though it had been.**

What was checked before publishing:

- the transcript file's SHA-256 matched the hash quoted alongside it;
- the five bundle digests it reported matched our own files byte-for-byte.

Neither of those establishes who ran anything. **Hashing a file supplied by one party
and comparing it to a number supplied by the same party is circular** — it demonstrates
that a file matches its own stated hash, and nothing more. The bundle digests are
published in this repository's own release notes, so reproducing them requires access
to the record, not execution of it.

That is precisely the class of unverifiable claim this project exists to refuse, and
it was accepted here because the result was welcome. A verification that arrives as
prose, through an intermediary, with no link the recipient controls, is testimony —
not evidence. The distinction is the entire thesis of this record, and it was not
applied to a claim in its own favour.

The transcript itself may well be genuine — its shape (a `/mnt/data/` sandbox path,
a complete and correct `MANIFEST.sha256` listing) is consistent with a real run, quite
possibly in a different session from the one that later objected. **Genuine is not the
same as demonstrated**, and only the second one belongs in an evidence record.

## What is preserved

`independent-verification-01-transcript.txt` (sha256
`9d7b0be65cbd3d28f60c73abb240774501c6f0bff7bbdc4eb6d7613927694d09`) is kept in place,
now labelled as **an unattributed artifact of unknown provenance**, not as evidence of
an independent run.

## What would make a future verification actually auditable

Adopting the suggestion made by the objecting party, and adding the part that closes
the provenance gap:

1. **Identify the artifact, not the person**: the verification-pack SHA-256, the exact
   repository commit it was built from, the transcript SHA-256, the run timestamp, and
   the toolchain versions.
2. **The verifier publishes the result themselves**, somewhere they control — a post, a
   gist, a signed message, an issue on this repository opened from their own account.
   The link must not run through us.
3. Ideally, a **signature over the transcript** by a key the verifier publishes
   independently.

Without at least (2), a report can only ever be recorded as *"a claim we received"*,
which is what this file now is.

## Status after withdrawal

```
implementation diversity                     yes
verification / operator diversity            NOT ESTABLISHED  (reopened)
public-repository provenance of the pack     not established
independent mining                           no
```

The one defect the exchange did surface is real and the fix stands on its own merits:
`scripts/ots_info.py` had an undeclared third-party dependency while the deposit
claimed none. `ctp/ots.py` now parses OpenTimestamps proofs using only the standard
library, cross-checked against the reference implementation on all five proofs and
tested under `python -S`. That fix was verified here, in this repository, and does not
depend on the withdrawn claim.

**The invitation is unchanged and unconditional.** Anyone may verify this record, and
anyone may mine the next block on the anchor chain. The next accepted block belongs to
whoever finds and submits it first.
