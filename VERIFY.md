# Verify this yourself

Everything this project claims is checkable from bytes, by you, without trusting us and
without asking us for anything. This page is the shortest honest path from a clone to a
verdict. If any step does not produce what it says here, that is a finding — please
open an issue with the output.

## What you will end up having checked

- Four evidence bundles, each carrying post-quantum signatures over real acquired
  evidence, verified **completely offline**.
- That each one's checkpoint is committed inside a real proof-of-work block on a live
  chain, and that the causal chain from the challenge block to the anchor block is
  unbroken.
- That the same bytes are attested by **public Bitcoin blocks**, via standard
  OpenTimestamps proofs that have nothing to do with this project.

## 0. The one hard dependency, stated up front

Verification needs **OpenSSL 3.5 or newer**, because the checkpoints are signed with
ML-DSA-87 and SLH-DSA-SHAKE-256s and those arrived in 3.5. This is genuinely recent, and
on many systems today the default `openssl` is 3.0–3.4, which **cannot** verify these
signatures. Check first:

```bash
openssl list -signature-algorithms | grep -E "ML-DSA-87|SLH-DSA-SHAKE-256s"
```

Two lines means you are ready. No output means you need a newer OpenSSL — recent
Debian/Fedora/Arch, Homebrew (`brew install openssl@3.5`), MSYS2 on Windows
(`C:\msys64\mingw64\bin\openssl.exe`), or any 3.5+ build on your `PATH`.

Python 3.10+ is the other requirement. To be exact about packages, because an earlier
version of this page was not:

- **Steps 2–6 need no third-party Python packages at all** — including the
  OpenTimestamps proof reader, implemented from the format in `ctp/ots.py` precisely so
  that checking a proof never requires a package index. Verify that claim yourself with
  `python -S scripts/ots_info.py vectors/valid/*.ots`.
- **Step 1, the test suite, additionally needs `pytest`** (`pip install pytest`). It is
  declared in `pyproject.toml` under the `test` extra.
- Only `scripts/ots_stamp.py` and `ots_upgrade.py` need the reference OTS library, and
  those *create* proofs over the network rather than checking them.

⚠️ **Ubuntu 24.04 LTS ships OpenSSL 3.0.13 and fails the check above**, with no apt path
to 3.5 — true of most current LTS distributions. Use a newer distro or container, or
build OpenSSL 3.5 from source (about half an hour). Stated here because a reviewer lost
that time finding it out.

Nothing touches the network except where it says so.

## 1. Clone and run the whole test suite

```bash
git clone https://github.com/machine-native/chronology-protocol
cd chronology-protocol
python -m pytest -q
```

Expected: `47 passed`, and — more to the point — **zero failures**. The count grows as
profiles are added, so treat the number as informational and the failure count as the
result. This exercises the canonical encoder, the interval algebra, the PQ signatures,
the Roughtime verifier, the OpenTimestamps proof reader, and full synthetic sandwich
round-trips *including* deliberate tamper cases that must fail.

## 2. Verify the sealed baseline (offline)

```bash
python scripts/verify_bundle.py vectors/valid/evidence-bundle.cbor
```

Expected: every check `true` except `BITCOIN_POW`, verdict **`PASS_PRE_POW`** — this is
the original sealed package, whose candidate block was deliberately never mined.

## 3. Verify the live-anchored bundle (offline)

```bash
python scripts/verify_bundle.py vectors/valid/evidence-bundle-live-anchored.cbor
```

Expected: **all 13 checks true**, verdict **`PASS`**. The same sealed evidence, now
carried in a block that really satisfies difficulty-1 proof-of-work.

## 4. Verify the three sandwich bundles (offline)

```bash
python scripts/verify_sandwich.py vectors/valid/reality-sandwich-bundle.cbor
python scripts/verify_sandwich.py vectors/valid/astro-sandwich-bundle.cbor
python scripts/verify_sandwich.py vectors/valid/roughtime-sandwich-bundle.cbor
```

Each should print **`SANDWICH_PASS`** with every check `true`. What each one proves:

| bundle | witnesses | what is special |
|---|---|---|
| `reality-sandwich` | 5 NTP operators | first real acquisition, causally bounded |
| `astro-sandwich` | 5 NTP + 1 camera | a photographed Moon inside the bounds |
| `roughtime-sandwich` | 2 Roughtime + 5 NTP | Ed25519-**signed** time evidence |

For the astronomical one you can also re-hash the original photographs and confirm they
are the exact frames the bundle commits to:

```bash
python scripts/verify_sandwich.py vectors/valid/astro-sandwich-bundle.cbor \
    --photos live/g2b-work/photos
```

`S_PHOTO_FILES: true` means the ten frames on disk are byte-identical to the ones
committed into a proof-of-work block. Open them: the handwritten code in the photographs
is the first 16 hex digits of the challenge derived from a block hash that existed five
minutes earlier. That binding is human-verifiable by design and is *not* claimed to be
cryptographic (see `docs/REALITY-SANDWICH.md` §6).

## 5. Check the anchors against the live chain (needs network)

> **If this step fails, it does not invalidate anything above.** Steps 1–4 and step 6
> are the load-bearing ones and they need no server of ours. This step talks to a
> seed node we operate, and a seed can be down, blocked, or unreachable from where
> you are sitting. The evidence bundles and their Bitcoin attestations remain
> checkable regardless; that separation is the whole design.
>
> Before concluding a seed is down, check whether the path is at fault: run
> `python live/check_seeds.py`, and test an unrelated host too. On 2026-08-21 this
> project briefly recorded the seed as down when the real cause was a local network
> fault — the seed was serving normally throughout.

Ask the chain itself, over its own wire protocol, rather than believing this repository:

```bash
python live/fetch_full_chain.py
```

This downloads every block from the public seed, verifies prev-hash linkage from the
fixed genesis, and writes `live/chain-blocks.hex`. Then confirm the four anchors are
really there:

```bash
python - <<'EOF'
import sys; sys.path.insert(0, ".")
from ctp.bitcoin_jan09 import block_hash, parse_single_tx_block, extract_anchor_from_coinbase
for i, line in enumerate(open("live/chain-blocks.hex")):
    raw = bytes.fromhex(line.strip())
    try:
        _, tx = parse_single_tx_block(raw)
        a = extract_anchor_from_coinbase(tx)
        print(f"epoch {a['epoch']}  height {i+1}  {block_hash(raw[:80])}")
    except Exception:
        pass
EOF
```

Expected (heights grow as the chain does; the hashes do not change):

```
epoch 0  height 221  00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b
epoch 1  height 222  0000000055cddf6e969747b574d17435af0799c839a3f149e020745b69419fa0
epoch 2  height 253  00000000eafb36b7c47b0a9ac975595b3e5ecc7006c85757bf5008380affe3ee
epoch 3  height 269  000000001a5380c4c618b2fd2dc4a8768e5cd807cf3122a24ce2fc4c548dc112
```

## 6. Check the Bitcoin attestations (independent of us entirely)

The evidence bundles are timestamped into the public Bitcoin blockchain with standard
OpenTimestamps proofs. Prefer the **official client** — it is not ours:

```bash
pip install opentimestamps-client
ots verify vectors/valid/evidence-bundle.cbor.ots
```

⚠️ **On Windows that client currently crashes** (`ots` depends on python-bitcoinlib,
which loads libssl through ctypes and fails there). It works on Linux and macOS. So
that no platform is stuck, this repository also ships a **standard-library-only reader,
implemented directly from the OpenTimestamps proof format** (`ctp/ots.py`, no
third-party imports at all — check it with `python -S`), which asks you to do the final
comparison yourself:

```bash
python scripts/ots_info.py vectors/valid/evidence-bundle.cbor.ots
```

It prints, for each attestation, a **Bitcoin block height** and the value that must be
that block's **merkle root**. You then check that against any node or explorer you
already trust — which is the point: the last step deliberately does not run our code.

### Worked example you can repeat right now

For `evidence-bundle.cbor` (sha256 `9fc2d7c7…`), the reader prints:

```
BITCOIN block 963190
  that block's merkle root must be: 6fb556ef0dab354fe0e7ad5f2f1262f18490f1fed0c2a915c9c5abb3de346e3d
BITCOIN block 963207
  that block's merkle root must be: 386b55af90bb5139e52c8b34500823b16f8eb053e1f04748a32004e3101567da
```

Ask a block explorer that has never heard of this project:

```bash
curl -s https://blockstream.info/api/block-height/963190          # -> block hash
curl -s https://blockstream.info/api/block/<that-hash> | grep merkle_root
```

Both roots match, and they were confirmed this way on 2026-08-21. That means the sealed
evidence bundle existed **before those Bitcoin blocks were mined** — a fact now secured
by Bitcoin's accumulated proof-of-work, not by us. Four of the five proofs carry
attestations (blocks 963190, 963207, 963408, 963413); the newest is still aggregating
and upgrades with `python scripts/ots_upgrade.py`.

If this repository vanished tomorrow, a saved bundle plus its `.ots` file plus the
Bitcoin blockchain would still prove when it existed.

## 7. Do something we have not done

The chain is open and mining is permissionless — the laboratory's own README says the
next block belongs to whoever finds it. If you mine one, or run your own sandwich, or
simply run the steps above and report what you saw, **you become the first independent
party in this record**, which is the one gap no amount of our own work can close. Every
acceptance record in this repository ends by saying so plainly.

## If something fails

Do not assume you did it wrong. A failure here is either a bug in our code, an error in
our claims, or a dependency problem — all three are worth reporting, and the first two
are worth more to us than a passing run. Open an issue with the command and its full
output.
