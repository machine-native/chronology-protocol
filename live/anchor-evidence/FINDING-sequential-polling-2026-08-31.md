# TIME_CONFLICT on epoch 5 was the acquisition method, not the witnesses

**Found 2026-08-31**, while assembling the epoch-5 bundle and noticing its
checkpoint carried `TIME_CONFLICT`.

## What the verdict appeared to say

Five NTP witnesses whose intervals had no three-way overlap, so the consensus
rule declined to produce one. Read naively: the servers disagreed about the time
by more than a second, and one or more of them is badly wrong.

## What actually happened

The witnesses are polled **one after another**, and each reports the time when
*it* was asked. Their monotonic timestamps are recorded in the evidence, so this
is checkable rather than inferred:

```
                  polled at        interval starts at
time.nist.gov      +0.000s              +0.000s
ptbtime1.ptb.de    +0.277s              +0.426s
time.google.com    +0.685s              +0.943s
time.windows.com   +1.127s              +1.168s
time.apple.com     +1.340s              +1.555s

polling span 1.340s          interval spread 1.555s
```

The spread tracks the polling order and the polling span. **No witness disagreed
with any other.** Five servers were asked at five different moments and each
answered correctly about its own moment.

Epoch 6, the same code against the same five servers, polled in 0.699 s and its
intervals spread 0.546 s — enough overlap to reach `CONSENSUS`.

## The actual defect

The consensus rule treats the intervals as **concurrent measurements of one
instant**. They are **sequential measurements of five instants** roughly 340 ms
apart. When the polling span exceeds the interval widths, overlap is
arithmetically impossible no matter how good the servers are.

So the verdict is decided by network latency on the day. Epoch 6 did not pass
because its witnesses behaved better; it passed because its round trips happened
to be quicker.

`TIME_CONFLICT` is also a misleading name for this. Nothing conflicted.

## What was NOT done, and why

**The protocol was not changed and no epoch was re-derived.** Epochs 1 through 6
are anchored in proof-of-work and stamped into Bitcoin. Retroactively widening
intervals to make an old verdict nicer would be exactly the manipulation this
project exists to make impossible, and epoch 5's bundle is already attested in
Bitcoin block 964841 carrying `SANDWICH_PASS_NO_TIME_CONSENSUS`. It stays as it
is.

**Epoch 5's causal claim is unaffected.** `B0 ≺ record ≺ C` comes from the
challenge structure — a value derived from block 529's hash inside the record,
and the record's digest inside block 530's coinbase. No part of it involves NTP.
What epoch 5 lacks is an agreed wall-clock instant, and it now lacks it for a
reason that is understood and written down.

## What this suggests for future acquisitions

Two options, neither implemented yet, both recorded so the choice is deliberate:

1. **Poll concurrently.** Five threads, one per witness, so the intervals
   describe the same instant. Removes the artefact at its source.
2. **Account for the offset.** The monotonic timestamps are already recorded, so
   each interval could be widened by its distance from a common reference
   instant. Honest, but it inflates uncertainty to compensate for a scheduling
   choice rather than a measurement limit.

The first is better. The second is a workaround for the first not being done.

Either is a protocol change and belongs in a version, not in a patch to a
running acquisition.
