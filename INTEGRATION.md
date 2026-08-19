# Live Jan09-Derivative Integration

The protocol package deliberately separates **construction**, **mining**, **transmission**, and
**acceptance evidence**.

## 1. Generate the sealed evidence bundle

```bash
python scripts/run_milestone1.py
python scripts/verify_bundle.py vectors/valid/evidence-bundle.cbor
```

Expected protocol verdict before mining: `PASS_PRE_POW`.

## 2. Obtain the current laboratory-chain tip

Record, from the target unmodified Jan09-derived node or an independently verified chain view:

- previous block hash
- previous block index's `GetMedianTimePast()` value
- `GetNextWorkRequired(pindexPrev)` for the candidate height

These values are evidence inputs. Do not infer them from local wall-clock filenames.

## 3. Build a candidate against that exact tip

Choose an `nTime` satisfying the historical contextual rule (`nTime > pindexPrev->GetMedianTimePast()`). The receiving node also independently rejects `nTime > GetAdjustedTime()+2 hours`.

```bash
python scripts/build_live_template.py \
  PREVIOUS_BLOCK_HASH \
  MEDIAN_TIME_PAST \
  NEXT_BITS_HEX \
  NEW_NTIME
```

This creates `reports/live-template.json`.

`NEW_NTIME` remains miner-supplied Bitcoin metadata. It is not a Chronology Protocol physical-time
measurement.

## 4. Compile the transparent nonce scanner

```bash
make miner
```

Its implementation is intentionally small and uses OpenSSL SHA-256.

Validate it against the published laboratory genesis:

```bash
native/mine_sha256d \
  0100000000000000000000000000000000000000000000000000000000000000000000008580a3211e4e3a77f12db073dd7fc6815751b8aa7599db46a675406cfdbda5aa7fdc706affff001da28efd01 \
  33394338 1
```

Expected hash:

`00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a`

## 5. Mine

Run the nonce scanner in disjoint ranges, or use an independently auditable SHA-256d implementation.

The expected work at difficulty 1 is substantial. Do not represent a template as a mined block.

When a valid header is found:

```bash
python scripts/finalize_mined_block.py FOUND_HEADER_HEX
```

The finalizer refuses any change except the nonce and refuses invalid PoW.

## 6. Submit over the v0.1 wire protocol

```bash
python scripts/submit_block_v01.py 127.0.0.1 18026
```

The sender uses the historical-style framing:

`magic[4] || command[12] || payload-size[4 LE] || payload`

with no modern message checksum and no mandatory `verack` step.

## 7. Prove acceptance

Network transmission is not acceptance.

Archive:
1. the exact raw block;
2. its SHA-256;
3. the target node version/source identity;
4. node log lines showing processing/acceptance;
5. block-index/active-chain evidence;
6. preferably an independent second node observing the block.

Only after those checks should the project change the milestone verdict from `PASS_PRE_POW` to
`PASS_LIVE_ANCHORED`.

## 8. Never patch Bitcoin for chronology semantics

Chronology Protocol remains a client of the anchor. Bitcoin does not parse GPS, Galileo, PQ
signatures, physical uncertainty or calendar mappings.
