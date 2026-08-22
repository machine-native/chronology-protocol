# Verification claims received

Reports from parties who ran the verifier, each recorded for exactly what it is.

The criterion this project set for itself requires two things: the artifact identified
(pack or commit, transcript, timestamp, toolchain), **and** the verifier publishing
their result somewhere they control, so the chain of custody does not run through this
project. **Claim #2 satisfies both.** Claim #1 satisfies only the first and is recorded
as a claim received, at the reporting party's own insistence.

The bar and the reason for it are in the withdrawn record,
[`INDEPENDENT-VERIFICATION-01.md`](INDEPENDENT-VERIFICATION-01.md).

---

## Claim #1 — 2026-08-22 — execution reported, artifacts identified

**Classification: a claim we received, backed by a complete execution transcript.
Criterion NOT closed** — by the reporting party's own assessment as well as ours.

### Artifact identification

```
verification pack sha256   128666ddcd1d21d5cdbb8fc85d3096c9d3e52aa36f05cc87f68bc5ad4ff3ce2b
repository commit          b70395c11edc12bc6831ff94910dc50830651c0c   (v0.4.1-14-gb70395c)
pack built (UTC)           2026-08-22T06:43:05Z
transcript sha256          2300b7224cae4fc3f95df2c5db1f939cfebbd9d546b2041061aa648e801ed9f9
toolchain reported         Python 3.13.5, pytest 9.0.2, OpenSSL 3.5.5
runtime reported           a sandboxed environment with no outbound network
```

Transcript preserved as `verification-claim-01-transcript.txt`; its hash was confirmed
on receipt. **That confirmation proves the file matches its stated digest and nothing
about who produced it** — the same limitation that caused the first record to be
withdrawn, stated here so it is not forgotten a second time.

### Reported results

```
pack sha256 vs stated          MATCH
sha256sum -c MANIFEST.sha256   110/110 OK
archive structure              111 files, no path-traversal entries; the only
                               unmanifested file is MANIFEST.sha256 itself
python -m pytest -q            43 passed, 0 failed
evidence-bundle.cbor           PASS_PRE_POW   (BITCOIN_POW false, as that vector intends)
evidence-bundle-live-anchored  PASS           (BITCOIN_POW true)
reality-sandwich-bundle        SANDWICH_PASS
astro-sandwich-bundle          SANDWICH_PASS
astro + supplied photographs   SANDWICH_PASS, S_PHOTO_FILES true
roughtime-sandwich-bundle      SANDWICH_PASS
ots parser                     PASS
ots parser under `python -S`   PASS
```

All five reported bundle digests match this repository's files byte-for-byte.

### What the reporting party explicitly declined to claim

They stated they could not retrieve the public Git commit from their runtime, so
**pack ↔ public repository byte identity is not established**; and that they did not
query a Bitcoin node or explorer, so **the five attestations were parsed but not
checked against public Bitcoin**. Their own summary:

> "The supplied verification artifact executes successfully and passes its complete
> local verification path." — not "every external provenance claim has independently
> been established."

They further concluded that they could not close the criterion because they have no
independent public identity from which to publish, and that publishing through this
project's account "would once again make the provenance path run through you."

**That reasoning is correct and is adopted.** A party declining to claim a status they
could have claimed is the strongest signal in this record.

### The defect it found — real, ours, fixed

`VERIFY.md` still described the shipped OTS reader as one that "uses only the
`opentimestamps` library" — stale wording left over from before the reader was
rewritten, and directly contradicting the corrected dependency claim earlier in the
same document. **Fixed**: it now reads "a standard-library-only reader, implemented
directly from the OpenTimestamps proof format," and points at `python -S` as the check.

This is the third real defect found by outside review in two days. The first two were
an undeclared dependency and a stale test count.

---

## Claim #2 — 2026-08-22 — **independent verification, publicly filed** ✅

**Classification: D-8 SATISFIED.** The first verification of this record by a party
outside the project, published by that party from an account they control.

**Issue [#1](https://github.com/machine-native/chronology-protocol/issues/1)** —
opened 2026-08-22T08:28:23Z by GitHub user **`naxytra`**.

### What a reader can check without asking anyone

- The issue is public, and GitHub timestamps it independently of this project.
- `naxytra` is **not** a member of the `machine-native` organisation and **not** a
  collaborator on this repository — verifiable through GitHub's own API. They had
  no write access to anything they verified.
- They cloned the repository themselves at commit
  `fc5933df265dd20ee9876d64511c6f0d3f604832`, rather than receiving a copy.
- Every digest in their report matches this repository byte-for-byte.

### What rests on the author's statement, and is recorded as such

That `naxytra` is a different person from the project author. **No reader can verify
that from the outside**, and it is inherent to reports of this kind — a single report
from a low-history account is weaker evidence than several from established ones.
It is stated here rather than glossed, and the remedy is more verifiers, not stronger
wording. The author has stated that `naxytra` is an independent entity.

### Their result

```
host          Ubuntu 24.04.3 LTS, OpenSSL 3.0.13 (too old for the PQ algorithms)
run inside    docker ubuntu:25.10 — Python 3.13.7, OpenSSL 3.5.3
commit        fc5933df265dd20ee9876d64511c6f0d3f604832

MANIFEST.sha256                     all OK
pytest                              48 passed
evidence-bundle.cbor                PASS_PRE_POW
evidence-bundle-live-anchored.cbor  PASS            (13/13)
reality-sandwich-bundle.cbor        SANDWICH_PASS   (20/20, burial 2)
astro-sandwich + --photos           SANDWICH_PASS   (22/22, S_PHOTO_FILES true)
roughtime-sandwich-bundle.cbor      SANDWICH_PASS   (21/21)
all five .ots proofs                digests match on disk
```

**They also confirmed a Bitcoin attestation against a third party.** For block 963190
the proof requires merkle root `6fb556ef0dab354f…46e3d`; blockstream.info returned
exactly that. No code of ours participates in that comparison.

**And they confirmed a recent fix in the wild.** Running natively on the host's
OpenSSL 3.0.13, the verifier reported `INDETERMINATE_TOOLCHAIN` with checks marked
`UNAVAILABLE` and an explicit "NOT A FAILURE OF THE EVIDENCE" note — rather than the
`FAIL` an earlier reviewer received, which had wrongly implied the evidence was bad.

### What they explicitly declined to claim

No mining attempted. Live-chain step not run. Only one of five Bitcoin attestations
independently checked. PQ verification performed in a container, not against the
host toolchain. No source-code audit — an execution result, not a review.

### Status after this report

```
implementation diversity        yes
verification diversity          YES — first independent verification (this report)
independent mining              still no
```

Mining remains open to anyone. Every block on the anchor chain was mined by this
project; the next accepted block belongs to whoever finds it.

---

## Standing invitation

Anyone may run [`VERIFY.md`](../../VERIFY.md). If you publish the result somewhere you
control, it closes the one criterion this project cannot close for itself.

Independent **mining** remains at zero — every block on the anchor chain was mined by
this project. The next accepted block belongs to whoever finds and submits it first.
