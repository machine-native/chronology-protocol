# Height 298 — mined by an FPGA this project built

On 2026-08-23 a Digilent Cmod A7-35T running a SHA-256d miner written for this
project found and won block **298** of the anchor chain. It is the first block on
this chain mined by purpose-built hardware rather than by software on a
general-purpose machine.

## The block

```
height        298
hash          000000004d255fbd71886cba88f5730185aed1a73fb2ac1a17dadd61c0016d48
prev          00000000b104e014af243351efacdab8966c56b7f07ab9e06b1a7a2e91871c22
nonce         1621531239
nTime         1787427471
nBits         0x1d00ffff
size          306 bytes
raw sha256    9bcf13f80a3ed8688071c2f63a5fb8e7b48c3886924cea47413150fb3d659c42
```

## The machine that found it

```
device        Xilinx XC7A35T (Cmod A7-35T), 12 MHz board oscillator
design        fpga/rtl/ -- 12 parallel SHA-256d cores, interleaved by nonce
clock         77.419 MHz, synthesised by an MMCM from the 12 MHz input
timing        +0.457 ns setup, +0.009 ns hold, met
measured rate 6.9854 MH/s
search        485.6 s of a single nTime
```

At difficulty 1 the expected search is 2³² hashes, or about 615 s at that rate.
485.6 s is an ordinary result — slightly lucky, not remarkably so.

## How to check it without trusting this file

```bash
python live/fetch_full_chain.py
```

That downloads every block from the public seed over the chain's own wire
protocol and verifies prev-hash linkage from the fixed genesis. Block 298 should
be the value above. Then re-derive the proof-of-work yourself:

```bash
python - <<'EOF'
import sys; sys.path.insert(0, ".")
from ctp.bitcoin_jan09 import block_hash, target_from_bits
raw = bytes.fromhex(open("live/chain-blocks.hex").read().split()[297])
h = block_hash(raw[:80])
print(h, int(h,16) <= target_from_bits(int.from_bytes(raw[72:76],"little")))
EOF
```

The block was confirmed this way on **two separate machines**: the desktop that
drives the FPGA, and the laptop this repository is developed on, which has never
had the board attached to it. Neither confirmation is independent of the project,
and that limitation is stated rather than glossed — see below.

## What this does and does not establish

**Does:** hardware designed and built here computed a real proof-of-work that the
network accepted. The nonce the board reported over UART, `1621531239`, is the
nonce in the block the seed now serves. Three independent implementations of this
chain's consensus hash now exist — Python, C, and this silicon.

**Does not:**

- **This is not independent mining.** Every block on this chain, including this
  one, was mined by this project. The FPGA is new hardware, not a new party.
  Independent mining remains at zero and this block does not change that.
- **The coinbase payload is not new evidence.** It reuses the epoch-0 anchor
  payload from `reports/verification.json`, because `mine` was run without
  `--payload-hex`. The block is a genuine proof-of-work win; its payload is a
  copy of an anchor that already existed. No new chronology claim is made by it.
- **The confirmations above are ours.** Both machines are operated by the author.
  A reader who wants outside confirmation should fetch the chain themselves; the
  instructions above need nothing from us but the seed, and the seed serves
  everyone.

## The mining path, for the record

The FPGA never decided validity. It reports nonces whose digest ends in a zero
word — a coarse filter that at difficulty 1 admits roughly 1 in 65,536 hashes
still above target. `scripts/fpga_host.py` re-checked the candidate against the
exact compact target before writing it to disk, and `scripts/submit_block.py`
re-derived the proof-of-work from the raw bytes again, and confirmed the parent
was still the chain tip, before anything was sent. Broadcasting required a typed
confirmation.

Nothing about that chain of custody depends on the hardware being correct. A bug
in the FPGA could have wasted the 485 seconds or missed a candidate; it could not
have produced a block the software path would accept as valid when it was not.
