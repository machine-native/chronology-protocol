# Contributing

**The contribution this project most needs is not code. It is a verification report
from someone who is not me.**

Everything here is checkable from bytes alone, and that is precisely why an outside
run matters more than a patch: no amount of additional code can establish that a
stranger, on their own machine, gets the result the documentation promises.

## The contribution that is actually wanted

Read [`CALL-FOR-VERIFICATION.md`](CALL-FOR-VERIFICATION.md). It takes about ten
minutes, needs no accounts, and runs entirely offline. [`VERIFY.md`](VERIFY.md) is
the longer walk-through if you want to understand what each step proves.

Then open an issue using the **verification report** template, or publish wherever
you like and link it.

Three things about such a report, none of them formalities:

**A failure is more useful than a pass.** If a command errors, paste the exact
output. That is a finding, and it will be recorded as found rather than quietly
fixed. Outside review has already produced three real defects this way — an
undeclared dependency, a stale test count, and a sentence contradicting the fix it
described — and an earlier reviewer's run exposed a fourth, arguably the worst: the
verifier reporting `FAIL` where it should have said `INDETERMINATE_TOOLCHAIN`,
implying the evidence was bad when only the toolchain was too old.

**"I could not check this" is a valid result.** It is not the same as "I checked
and it failed", and the difference matters enough that the codebase enforces it in
several places. Say which one you mean, and say if you skipped a step.

**It has to come from an identity you control.** Not relayed through me. A report
was once recorded here and then withdrawn precisely because its provenance ran
through the project author, who accepted it because the result was flattering. That
episode is kept in the repository rather than deleted:
[`live/anchor-evidence/INDEPENDENT-VERIFICATION-01.md`](live/anchor-evidence/INDEPENDENT-VERIFICATION-01.md).

Understating is welcome. Overstating is not.

## Security findings

Do not open a public issue. See [`SECURITY.md`](SECURITY.md), and mail
**parthms.id@gmail.com**.

## If you do want to send code

Pull requests are welcome but rare here, and two constraints are worth knowing
before you spend time.

**The verification path is standard-library only.** `ctp/` and `scripts/verify_*.py`
must not acquire third-party imports — an outside reviewer has to be able to check
this repository with nothing but Python and OpenSSL. The test suite may use `pytest`,
and that distinction is itself pinned by a test.

**Anchored evidence is immutable.** Bundles under `vectors/valid/`, their `.ots`
proofs, and anything under `live/` that a checkpoint commits to have been mined into
real proof-of-work blocks. They are not regenerated, reformatted or tidied. If one is
wrong, the fix is a new record that says so — never an edit that makes the old claim
quietly disappear.

Otherwise:

```bash
python -m pytest -q                          # must pass with zero failures
python scripts/confirm_attestations.py       # attestations still match the chain
```

Prose is held to the same standard as code: claims in documentation are pinned by
tests where they can be, because three separate stale-documentation defects have been
found here by readers.

## Licence

Apache-2.0. By contributing you agree your contribution is licensed under it.
