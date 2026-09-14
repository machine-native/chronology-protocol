# Corrections to sealed acceptance records

The acceptance records in this directory are sealed: `ACCEPTANCE.md` is named by digest
in `live/MANIFEST-live.sha256`, and every `*ACCEPTANCE*.md` is treated the same way.
They are not edited after the fact. Where a sentence in one of them has since been found
to overstate or mis-describe what the evidence shows, the correction is recorded here,
beside the record, with the date. The original sentence stands as written; the corrected
reading is what the project asserts today.

Each entry gives the file, the sentence as sealed, and the corrected reading.

## 14 September 2026

### `ACCEPTANCE.md` — "a party outside that VM"

As sealed (section *Limits, stated plainly*):

> except that this block itself was mined and submitted by a party outside that VM,
> which is a first for this chain beyond its own operator.

Corrected reading: the block was mined and submitted from a machine other than the
laboratory VM, by the same operator — two machines, one operator. It is not a block from
a second party, and it does not add operator diversity to the chain.

### `ROUGHTIME-SANDWICH-ACCEPTANCE.md` — "that same independent miner"

As sealed (the burial note in the anchor listing):

> the epoch-1 and epoch-2 bundles were buried 2 and 10 deep respectively by that same
> independent miner.

Corrected reading: buried by the laboratory's own miner, the second of two machines run
by one operator. The miner is a separate implementation and a separate machine; it is
not an independent party.

### `ROUGHTIME-SANDWICH-ACCEPTANCE.md` — "classic protocol dead everywhere"

As sealed (section *What is cryptographically new*):

> Two of the four ecosystem servers were unreachable (classic protocol dead everywhere;
> `roughtime.se` and `roughtime.int08h.com` silent on both wire formats)

Corrected reading: the classic protocol was not served by any endpoint tried in that
session. Four endpoints were tried; nothing was established about endpoints that were
not.
