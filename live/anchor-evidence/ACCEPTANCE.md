# Live-Anchor Acceptance Evidence — height 221, 2026-08-19

This document records the completion of the external gate declared in
`RELEASE_STATUS.json` of the sealed v0.1.0 package: construct against the live tip,
mine real proof-of-work, submit to a running Jan09-derived node, capture acceptance
evidence from unmodified node(s). Executed 2026-08-19 by parthod0x.

## The anchor block

```
block hash        00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b
height            221
parent            000000004ccc5b55de9727622be0e2fb2ae17c4e994b504c1914e366a1ce6f7c  (height 220)
nTime             1787136965 = 2026-08-19T10:56:05Z
nBits             0x1d00ffff  (difficulty-1, real work)
nNonce            2757362010
raw block         306 bytes, sha256 5d5ccd04ef744ace9683ae2c33ff4aea2fc39d06b0735b85203e8ff37829677b
coinbase          98-byte scriptSig carrying the sealed 96-byte CHRN checkpoint payload
subsidy payee     the chain's genesis P2PK key (04c0414c…) — the anchoring party holds no key
                  to this output and claims nothing on this chain
```

The 96-byte checkpoint payload in this block's coinbase is byte-identical to the payload
sealed in v0.1.0's evidence bundle (`sealed_evidence_bundle_sha256 9fc2d7c7…`). Nothing
was re-signed; the pre-PoW seal and the live anchor commit to the same bytes.

## Target chain

Bitcoin (2026), the original-bitcoin-laboratory experimental chain: genesis
`00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a`, magic `f00ba726`,
port 18026, public seed `bitcoin.bitcoin-lab.org:18026` (168.144.27.117). Not money;
experimental; mining is open by that project's own statement ("the next block belongs
to whoever finds it").

## Context acquisition (evidence inputs, not wall-clock inference)

Fetched over the v0.1 wire and re-derived from raw block bytes
(`live/fetch_tip_context.py`; final winning context in
`live/anchor-evidence/live-template-height221.json`):

```
parent (height 220)      000000004ccc5b55de9727622be0e2fb2ae17c4e994b504c1914e366a1ce6f7c
GetMedianTimePast        1787122655   (median of the 11 tail-header nTimes, fetched raw)
GetNextWorkRequired      0x1d00ffff   (height 221 is not a 2016-block retarget boundary)
chosen nTime             1787136965   (> MTP; within the +2h rule at the receiving nodes)
```

## Mining

The package's transparent scanner (`native/mine_sha256d.c`, OpenSSL SHA-256) was
compiled and first validated against the published laboratory genesis vector
(nonce 33394338 → `00000000ad12f3ec…`, reproduced exactly). Eight processes scanned
disjoint nonce ranges (~0.5 MH/s each on this machine).

Disclosed in full — two earlier candidates were mined and lost their height races to
the laboratory VM, which mines the same chain at a ~45–64 min cadence:

```
candidate 1  00000000ccd47c6b542030a0609e7e2939dbac23ad9d1e50e23477ad9b9f450d
             parent 00000000eadea588… (height 218), lost height 219 to 00000000cd6121c1…
candidate 2  00000000eaa0fabf769b617429973096303bc282eddc47c5a12f3c8eede59b16
             parent 00000000cd6121c1… (height 219), lost height 220 to 000000004ccc5b55…
candidate 3  00000000fc80fe4f…  — parent 000000004ccc5b55… (height 220): ACCEPTED as height 221
```

The losing candidates carry valid PoW for stale parents; they are ordinary orphan-race
losses, stated here rather than left to be discovered.

## Acceptance evidence, four independent forms

**1. The operated public seed adopted the block as its active tip.** Post-submit
`getblocks`-from-genesis inventory returned 221 hashes ending in ours
(`live/anchor-evidence/tip-context-post-submit.json`). The seed runs the laboratory's
netnode — a different implementation from the client that built the chain, and from
the tooling that mined this block.

**2. Full-chain re-download with independent linkage verification.** All 221 blocks were
re-fetched raw from the seed and prev-hash linkage was verified from the fixed genesis to
our block (`live/fetch_full_chain.py` → `live/chain-blocks.hex`,
sha256 `2572fac346d8f289d7b84321e64d3ec14b90ed25fc207970a64db5ce1518c916`).

**3. An unmodified released Jan09-derived client accepted the block into its best chain.**
`bitcoin.exe` from the published v0.1.5 release
(sha256 `c3f15fc5b7bd80f4d08fe5ff356256214734eb1a3e4a7c953c9e8fc8453d2c7d`, matching the
laboratory's own executed-binary bindings) was run with a fresh datadir and fed the chain
over the v0.1 wire. Its log (`live/node-evidence/debug.log`,
sha256 `aadc1576c8e5ad2e599bacefdb7cde49576a4aee9d2e44df1c5a337f48f3b302`) shows exactly
221 `ProcessBlock: ACCEPTED` lines, prints our block with the CHRN payload visible in the
coinbase, and ends:

```
CBlock(hash=00000000fc80fe, ver=1, hashPrevBlock=000000004ccc5b, hashMerkleRoot=42b6b9,
       nTime=1787136965, nBits=1d00ffff, nNonce=2757362010, vtx=1)
AddToBlockIndex: new best=00000000fc80fe  height=221
ProcessBlock: ACCEPTED
```

Its stored chain (`live/node-evidence/datadir/blk0001.dat`, 49,678 bytes,
sha256 `5a19fc5677acd328cde2ea6828f978a42041675ee9922ad079a269ef004c16e8`) contains the
block. The client's GUI reported 222 blocks (heights 0–221).

**4. The bundle verifier's own verdict.** The live-anchored evidence bundle
(`vectors/valid/evidence-bundle-live-anchored.cbor`,
sha256 `9fbccb5b37e5c3798f557d9de91f1d60a16b86dd817544e2967fdf729d6561a4`) — the sealed
bundle with only the candidate block and its median-time-past replaced by the mined
reality — verifies with **all 13 checks true, verdict `PASS`**, including `BITCOIN_POW`.

## Limits, stated plainly

- Difficulty-1 work is real but small; this proves anchoring mechanics and causal
  ordering, not security margin.
- The seed is operated by the same laboratory that runs the mining VM; implementation
  diversity (netnode vs the 2009-derived client) is real, operator diversity is not —
  except that this block itself was mined and submitted by a party outside that VM,
  which is a first for this chain beyond its own operator.
- The local v0.1.5 client was fed the chain by us rather than discovering peers itself
  (the 2009 bootstrap channels are dead); every validation it performed was its own.
- Burial depth at capture time was 0 (our block is the tip). Subsequent laboratory
  blocks building on it will bury it; that check can be re-run at any time against the
  seed with `live/fetch_tip_context.py`.

## Naming note (for the laboratory's registry)

Port 18026 is assigned to Bitcoin (2026) in the laboratory's NAMING-AND-REFERENCING §3b.
The Chronology Protocol uses that port strictly as a wire *client* of that chain — it
runs no chain and no node of its own. If CHRN ever grows its own P2P network, it must
claim its own port assignment rather than reuse 18026.
