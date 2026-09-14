# The two manifests, and why there are two

An outside reviewer ran `sha256sum -c MANIFEST.sha256` on a fresh clone and got
five failures. They were right, and their framing was exactly correct (private
correspondence, quoted here):

> "That's a rhetorical wound out of all proportion to the actual defect […] but
> `sha256sum -c MANIFEST.sha256` is the first thing a skeptic runs on a repo whose
> banner claim is *checkable from bytes alone*."

Here is what was actually wrong, and what each file now means.

## `MANIFEST-v0.1.0-SEALED.sha256` — a historical seal, not a live check

This is the manifest of the **original sealed v0.1.0 package** (59 files), written
once on 2026-08-19 and never regenerated. It attests what that package contained.

As of 14 September 2026, **15 of its 59 entries no longer match the working tree, and
that is expected.** The drift is confined to three classes of file, and the list is
re-derivable with `sha256sum -c MANIFEST-v0.1.0-SEALED.sha256`:

- **documents**, edited through the releases up to v0.5.0 and in the September 2026
  corrections: `CLAIMS.md`, `LICENSING.md`, `README.md`, `RELEASE_NOTES.md`,
  `RELEASE_STATUS.json`, `SECURITY.md`, `pyproject.toml`;
- **verifier source**, changed on 2026-08-22 by the outside-review fixes (commits
  `24ccc74` and `fc5933d`: a check the toolchain cannot perform is reported
  `INDETERMINATE`, not `FAIL`) and once more since: `ctp/pq.py`, `ctp/verify.py`,
  `scripts/verify_bundle.py`, `scripts/build_live_template.py` (`370af79`),
  `scripts/release_audit.py` (`6141d83`), and `ctp/__init__.py` (version string only);
- **tests** that exercise the changed code: `tests/test_pq.py`, `tests/test_renewal.py`.

The remaining 44 files — every sealed evidence vector under `vectors/`, the five
schemas, the native miner, the remaining protocol modules under `ctp/`, and the
sealed reports — are byte-identical to the day they were sealed, which is the property
that actually matters. The sealed evidence bundle in particular is unchanged, and its
OpenTimestamps proof still verifies against it.

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
or the manifest was not regenerated — both are worth reporting. A test,
`tests/test_docs_consistency.py::test_manifest_covers_every_tracked_file`, fails when a
tracked file is missing from the manifest, so an omission is caught before release
rather than by a reader.

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

## Redactions

On 14 September 2026 a handful of evidence files had local paths, a host name, a machine
name, adapter models, private and public network addresses and a country name replaced
by placeholders. The digests recorded at capture time in `live/MANIFEST-live.sha256` and
`live/anchor-evidence/ACCEPTANCE.md` are left as they were, for the reason given above
about seals; the digests of the redacted copies, and exactly what changed, are in
[`live/REDACTIONS.md`](live/REDACTIONS.md). `MANIFEST.sha256` lists the redacted copies.

One entry of `live/MANIFEST-live.sha256` differs from the tree for a reason unrelated to
redaction: it records `live/chain-blocks.hex` as captured at height 221, and that file
was regenerated at height 298 on 2026-08-23 (commit `c8b298d`) when the FPGA block was
confirmed. The capture digest stands; the current file is listed in `MANIFEST.sha256`.

Sentences in the sealed acceptance records that have since been found to overstate what
the evidence shows are not edited; they are corrected beside the records, in
[`live/anchor-evidence/CORRECTIONS.md`](live/anchor-evidence/CORRECTIONS.md).
