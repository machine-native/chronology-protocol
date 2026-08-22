# Wanted: one independent verifier

This project has a record of physical-time observations sealed with post-quantum
signatures and anchored into two proof-of-work blockchains. Everything it claims is
checkable from bytes alone.

**One thing is missing, and it cannot be produced by writing more code: nobody outside
the project has verified it and said so publicly.**

That is the whole ask. It takes about ten minutes.

---

## What you do

**1. Clone it yourself.** Not a copy sent to you — this step is what proves the files
are the published ones, and it is the part a sandboxed environment could not do.

```bash
git clone https://github.com/machine-native/chronology-protocol
cd chronology-protocol
git rev-parse HEAD          # note this commit
```

**2. Check the one hard dependency.** Verification needs OpenSSL **3.5 or newer**,
because the checkpoints use ML-DSA-87 and SLH-DSA-SHAKE-256s:

```bash
openssl list -signature-algorithms | grep -E "ML-DSA-87|SLH-DSA-SHAKE-256s"
```

Two lines means you are ready. Nothing appears on OpenSSL 3.0–3.4 — get a 3.5+ build
(recent Debian/Fedora/Arch, `brew install openssl@3.5`, or MSYS2 on Windows).
Python 3.10+ is the only other requirement. **No third-party Python packages are
needed.**

**3. Run it.** Everything here is offline — no network, no accounts, nothing of ours
running on your machine:

```bash
python -m pytest -q
python scripts/verify_bundle.py   vectors/valid/evidence-bundle.cbor
python scripts/verify_bundle.py   vectors/valid/evidence-bundle-live-anchored.cbor
python scripts/verify_sandwich.py vectors/valid/reality-sandwich-bundle.cbor
python scripts/verify_sandwich.py vectors/valid/astro-sandwich-bundle.cbor --photos live/g2b-work/photos
python scripts/verify_sandwich.py vectors/valid/roughtime-sandwich-bundle.cbor
python scripts/ots_info.py        vectors/valid/*.ots
```

**4. Publish what you got — from your own account.** This is the part that matters.

> Open an issue: **https://github.com/machine-native/chronology-protocol/issues/new**

Paste your actual output. Include your commit hash, OS, Python and OpenSSL versions.
A gist, blog post, mailing-list message or signed statement works equally well — the
only requirement is that **it comes from an identity you control, not relayed through
us.** Then, if you like, link it in an issue so it can be found.

That is it. You are done.

---

## Please do not round anything up

If a command fails, **that is more valuable than a pass** — send the exact output.
If you skip a step, say so. If you cannot check something, say that too.

A previous report was recorded here and then **withdrawn**, because its provenance ran
through the project author rather than the verifier, and the author accepted it anyway
because the result was flattering. That episode is preserved in the repository at
[`live/anchor-evidence/INDEPENDENT-VERIFICATION-01.md`](live/anchor-evidence/INDEPENDENT-VERIFICATION-01.md).
Outside review has since found **three real defects** — an undeclared dependency, a
stale test count, and a stale sentence contradicting a fix — every one of which is
credited and fixed.

So: understating is welcome, overstating is not, and finding something broken is the
best outcome available.

## What your run would and would not establish

**Would**: that the post-quantum signatures verify; that every claimed measurement
re-derives deterministically from raw recorded network packets rather than being
asserted; that the Merkle trees, consensus intervals and checkpoint chain are
internally consistent; that the embedded blocks satisfy their own stated
proof-of-work; that the header linkage holds; that the deliberate tamper cases fail as
designed; and — since you cloned it yourself — that these are the published files.

**Would not**: that any time source told the truth. This protocol bounds *when*
evidence was acquired, never whether its content is correct. Full limits:
[`CLAIMS.md`](CLAIMS.md).

---

## Optional, and harder: mine a block

The anchor chain is open and permissionless. Every block on it so far was mined by
this project — so an outsider-mined block would close the last gap outright.

```bash
python live/fetch_full_chain.py     # confirm you can reach the chain
bash live/race.sh live/sandwich-work/payload.hex
```

It fetches the current tip, builds a candidate, splits the nonce space across your
cores, mines, submits to `bitcoin.bitcoin-lab.org:18026`, refetches the chain, and
declares success **only if your block became the active tip**. Needs raw TCP on port
18026 and roughly twenty minutes of CPU. Difficulty is 1; the coins are valueless and
explicitly not money.

The next accepted block belongs to whoever finds it.

---

*Full walkthrough with expected outputs: [`VERIFY.md`](VERIFY.md).
Licence Apache-2.0. Nothing here asks you to trust the author — that is the point.*
