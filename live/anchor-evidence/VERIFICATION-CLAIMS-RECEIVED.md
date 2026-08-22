# Verification claims received

Reports from parties who ran the verifier. **None of these closes the project's
independent-verification criterion**, which additionally requires the verifier to
publish their result somewhere they control, so the chain of custody does not run
through this project. Each is recorded here for exactly what it is: a claim we
received, with its artifacts identified so a reader can weigh it.

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

## Standing invitation

Anyone may run [`VERIFY.md`](../../VERIFY.md). If you publish the result somewhere you
control, it closes the one criterion this project cannot close for itself.

Independent **mining** remains at zero — every block on the anchor chain was mined by
this project. The next accepted block belongs to whoever finds and submits it first.
