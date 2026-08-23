# Binding an external record into a reality sandwich

**Status: specification. No binding has been performed.** The worked example
below is real arithmetic over a real shipped bundle, and every value in it can be
recomputed from this repository — but no SATROOT event, sensor batch or other
external record currently carries a binding tag. When one does, it will be
recorded in `live/anchor-evidence/` like every other claim here, and this line
will say so.

## What this is for

A reality sandwich proves that an *acquisition* happened between two
proof-of-work blocks. Plenty of useful records are produced by other systems —
a SATROOT event, a batch of sensor readings, a build artifact — and those systems
can prove authorship, integrity and ordering, but not *time*.

That gap is specific and it is not closed by any amount of signing:

| mechanism | establishes | leaves open |
|---|---|---|
| digital signature | which key produced these bytes | when |
| hash chain / sequence number | that B came after A | when either happened |
| device attestation | the software state that ran | whether the clock was right |
| a trusted timestamp service | what a server asserted | whether the server was honest |

A sensor with a correct key and a wrong clock produces perfectly valid signed
evidence. So does one whose operator set the clock deliberately.

## The asymmetry

The obvious construction is to put the record's hash into the sandwich. That is
half a binding, and it is the weaker half:

```
sandwich commits to H    =>    H existed BEFORE B1          upper bound
```

It says nothing about when `H` was made. A record produced last year can be
committed today, and the bytes look identical either way. **Publication order is
not creation order.**

The lower bound has to travel the other way. The challenge

```
q = SHA-256( "CHRONOLOGY/SANDWICH-CHALLENGE/v1" || 0x00 || hash(B0) || session_id )
```

cannot be computed before `B0` is mined, so a record *containing* a value derived
from `q` could not have existed before `B0` did:

```
record commits to q      =>    record created AFTER B0      lower bound
```

Both directions, and only both, give the sandwich property:

```
        q ──────────────────►  external system
                                     │  record is signed WITH the tag inside it
                                     ▼
                                     H = sha256(record)
        H ◄──────────────────  sandwich evidence blob

                    B0  ≺  record  ≺  B1
```

This is the same structure as the rolling-code photographs, where the code must
be visible *in the frame* rather than quoted afterwards. A reference added later
proves nothing about the moment; a value that could not have been guessed does.

## The binding tag

The external record carries a derived tag, not `q` itself:

```
binding_tag = SHA-256( "CHRONOLOGY/EXTERNAL-BINDING/v1" || 0x00 || q || system_id )
```

Deriving rather than embedding does two things. Two systems bound to the same
session get different tags, so a record in one cannot be correlated with a record
in the other. And a system with a short field can carry a prefix of the tag
without leaking the challenge that other bindings in the same session depend on.

`system_id` is a short UTF-8 label chosen by the external system — `SATROOT1`,
`SENSOR-BATCH/v1`. It is part of the tag, so a tag minted for one system does not
bind a record in another.

## Verdicts

`verify_binding()` names what was established rather than collapsing to
pass/fail, because the two halves are genuinely different claims:

| verdict | meaning |
|---|---|
| `BOUND` | both directions: `B0 ≺ record ≺ B1` |
| `UPPER_ONLY` | sandwich commits to the record, but the record carries no tag — **it may predate B0 by any amount** |
| `LOWER_ONLY` | the record carries the tag, but nothing bounds it from above |
| `UNBOUND` | neither |

A verifier that returned "pass" for `UPPER_ONLY` would let a backdated record
wear a sandwich. That is the specific mistake this vocabulary exists to prevent,
and it is the one a caller in a hurry would otherwise make.

## Worked example

Real values, from `vectors/valid/reality-sandwich-bundle.cbor` in this
repository. Recompute them yourself:

```
B0 height       221
B0 hash         00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b
session_id      01711a5df184e30ac370e6502ddd7ad8ec70cf2994e0c76c13c2d7e155677362
q               6bfc8e3da4f18f8c59fae11bce0e311b1d19bac6ca1bd6e1e1ff77c3205aeb34

binding tag for system_id "SATROOT1":
                887a0ec3e7ad5f30a4328a9872658f43c20ecdf2b962e5fa4dbd7de65a8c5b88
```

```bash
python - <<'EOF'
import sys, hashlib; sys.path.insert(0, ".")
from ctp.sandwich import SandwichBundle, challenge
from ctp.bitcoin_jan09 import block_hash
from ctp.binding import binding_tag
b = SandwichBundle.from_bytes(open("vectors/valid/reality-sandwich-bundle.cbor","rb").read())
q = challenge(block_hash(b.b0_raw[:80]), b.session_id)
print(q.hex())
print(binding_tag(q, "SATROOT1").hex())
EOF
```

A SATROOT event carrying that tag — this is the shape, not a real event:

```json
{"root_id":"38ff9da029e66ee9b6a1b175025388caf7fb6d3bb0273812737d7dd6b347c473:0",
 "state_hash":"sha256:34049329f152c388cad547440b32213d48be583c0fa16d93a94582f7399fde58",
 "chrn_binding":"887a0ec3e7ad5f30a4328a9872658f43c20ecdf2b962e5fa4dbd7de65a8c5b88"}
```

The `root_id` and `state_hash` above are the genuine values from SATROOT's
recorded BSV mainnet anchor. The `chrn_binding` field is the proposal: **no
SATROOT event contains one today.**

## How the two chains divide the work

The composition uses two blockchains for two different jobs, and neither
substitutes for the other:

- **Bitcoin, via OpenTimestamps** — *"these bytes existed before time T"*. Free,
  and backed by the largest accumulated proof-of-work there is. Used for the
  outer attestation on evidence bundles.
- **The anchor chain, via a mined block** — *"this checkpoint is buried under
  work that did not exist when the challenge was issued"*. This is what makes
  `q` unguessable and what closes the sandwich.
- **BSV, via a one-satoshi root witness** — SATROOT's namespace handle and state
  commitments. Requires cheap, frequent, dust-level writes, which is what that
  chain is economical for and Bitcoin is not.

A one-satoshi UTXO as a namespace handle does not work on a chain where a dust
output costs more than it is worth. The split follows from the mechanics, not
from preference.

## What this does not do

- **It does not verify the external record.** Whether a SATROOT event is validly
  signed is SATROOT's question, answered by SATROOT's verifier. This module reads
  the record as opaque bytes and establishes only when those bytes existed.
- **It does not make a clock trustworthy.** It bounds a record between two
  blocks. The width of that interval is whatever the acquisition took; it is not
  a timestamp and must not be reported as one.
- **It does not survive a record being re-serialised.** The binding is over exact
  bytes. A system that re-encodes its records — reordering JSON keys, changing
  whitespace — breaks the hash and therefore the upper bound. Bind the canonical
  serialisation, or bind a digest the system already treats as stable.
- **It has not been exercised against a live external system.** Until it has,
  every claim on this page is about arithmetic, not about practice.
