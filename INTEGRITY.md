# The two manifests, and why there are two

An outside reviewer ran `sha256sum -c MANIFEST.sha256` on a fresh clone and got
five failures. They were right, and their framing was exactly correct:

> "That's a rhetorical wound out of all proportion to the actual defect […] but
> `sha256sum -c MANIFEST.sha256` is the first thing a skeptic runs on a repo whose
> banner claim is *checkable from bytes alone*."

Here is what was actually wrong, and what each file now means.

## `MANIFEST-v0.1.0-SEALED.sha256` — a historical seal, not a live check

This is the manifest of the **original sealed v0.1.0 package** (59 files), written
once on 2026-08-19 and never regenerated. It attests what that package contained.

Five of its entries no longer match the working tree, and **that is correct and
expected**: `README.md`, `CLAIMS.md`, `LICENSING.md`, `RELEASE_NOTES.md` and
`RELEASE_STATUS.json` have all been edited since, through the releases up to v0.4.1.
The remaining 54 files — the protocol source, the schemas, the sealed evidence
vectors — are byte-identical to the day they were sealed, which is the property that
actually matters.

The defect was never the drift; it was that a historical seal was named as though it
were a current integrity check, so a skeptic's first command printed a warning with
no explanation. It has been renamed rather than regenerated, because **regenerating a
seal destroys the only thing a seal is for.**

The v0.1.0 package is independently anchored anyway: its archive hashes to
`8850a4639559244f344f5416fe7a2e7257189449bb28b8f3c1825fe0ad95bb7b`, recorded in the
first commit of this repository and in `RELEASE_NOTES.md`.

## `MANIFEST.sha256` — the current tree

Regenerated at each release over every tracked file. This is what to run on a clone:

```bash
sha256sum -c MANIFEST.sha256
```

It should report **OK for every line**. If it does not, either your clone is damaged
or the manifest was not regenerated — both are worth reporting.

Be clear about what it proves: it detects corruption in transit and accidental
modification. It does **not** prove authorship, because whoever writes the files can
write the manifest. Authenticity comes from elsewhere in this record — the sealed
evidence bundles, their post-quantum signatures, and the OpenTimestamps proofs
anchored in public Bitcoin blocks, none of which can be forged by editing a file here.

## What each layer is actually good for

| layer | detects | can it be forged by us? |
|---|---|---|
| `MANIFEST.sha256` | transit corruption, accidental edits | yes — regenerate it |
| `MANIFEST-v0.1.0-SEALED.sha256` | drift from the original package | no, without also rewriting history |
| PQ signatures in the bundles | any change to the evidence | not without the private keys, which were discarded |
| Bitcoin attestations (OTS) | that the bytes existed before a given block | no |

A verifier who only checks the first row has checked the weakest link. `VERIFY.md`
walks all four.
