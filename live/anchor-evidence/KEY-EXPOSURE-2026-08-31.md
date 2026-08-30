# Signing keys published by mistake — epochs 4 and 5

**Found 2026-08-31.** Recorded here rather than quietly cleaned up, because a
project about evidence does not get to hide its own.

## What was exposed

26 post-quantum private signing keys, in two acquisition directories:

```
live/g6-work/keys/            epoch 4, committed 2026-08-23 in 1e76c4e
live/satroot-bind-work/keys/  epoch 5, committed 2026-08-29
```

Each directory holds `mldsa87.pem` (ML-DSA-87) and `slh256s.pem`
(SLH-DSA-SHAKE-256s) for the checkpoint signer, each NTP witness, and — in
epoch 4 — the camera witness. The matching `.pub.pem` files are public by
design and are not part of this.

They were pushed to a public repository and were readable for eight days and two
days respectively.

## How

`.gitignore` listed acquisition directories one by one:

```
live/sandwich-work/keys/
live/g2b-work/keys/
live/g5-work/keys/
```

Every new acquisition therefore needed a new line, and until someone added it the
keys were not ignored at all. Two were missed. The failure mode is that nothing
announces it: the commit succeeds, the tests pass, and the keys are simply there.

It is now `live/*/keys/`, which covers every directory that exists or will. A
pattern cannot be forgotten the way a list can.

## What this does and does not compromise

**Evidence already anchored is unaffected.** Epochs 4 and 5 are committed into
proof-of-work blocks 322 and 479 and stamped into Bitcoin by OpenTimestamps.
Holding the signing keys does not let anyone alter a checkpoint that is already
buried under work, and it does not let them produce a different past. The
anchoring exists precisely so that a key leak cannot reach backwards, and here it
did its job.

**What a holder could do** is sign new material as though these witnesses
produced it — a fabricated epoch claiming to continue the chain, for instance.
At difficulty 1 the accompanying block is cheap to mine. Such an artifact would
not chain to the anchored checkpoints without redoing their proof-of-work, so it
is detectable by anyone who checks against the record, but it would exist and it
would carry genuine signatures.

**Future acquisitions are not automatically compromised.** Keys are generated
fresh per acquisition directory, so epoch 6 and everything after use material
these keys cannot produce.

## What was done

1. `.gitignore` changed from a list to `live/*/keys/`.
2. The 26 keys removed from tracking with `git rm --cached`. They remain on the
   working machine, since deleting them would destroy the ability to verify the
   epochs they signed.
3. This note.

4. **History rewritten and force-pushed**, 2026-08-31. `git filter-repo`
   removed every key blob from all 71 commits, verified as zero matching objects
   across `git rev-list --all --objects`.

The first version of this note said history would not be rewritten, on the
reasoning that rewriting breaks clones while un-publishing nothing. That
reasoning depended on someone having cloned. The operator confirmed nobody had,
which makes the rewrite cheap and the argument against it void, so it was done.
Every commit hash prior to the rewrite is therefore superseded. A pre-rewrite
bundle is retained offline.

## What is deliberately not claimed

**That the keys were never disclosed.** They were pushed to a public repository
and were fetchable for eight days and two days. GitHub may retain unreferenced
objects, caches and forks beyond a force-push, and no rewrite reaches those. The
correct assumption remains that this material is compromised; the rewrite reduces
casual discovery and nothing more.

**That the exposure was harmless.** An evidence project leaking its signing keys
is a real failure. The bounded consequence is a property of the anchoring design,
not of the mistake.

**That the keys need rotating.** They already do, structurally — each acquisition
mints its own, so there is nothing ongoing to rotate. The exposed material signs
two epochs already fixed in proof-of-work.
