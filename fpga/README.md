# FPGA miner — Cmod A7-35T (work in progress)

A SHA-256d miner in hardware for the anchor chain: our own silicon mining our own
chain. Started 2026-08-21.

## Status

| piece | state |
|---|---|
| `rtl/sha256_core.v` — compression core, 1 round/cycle | **simulated, all vectors pass** |
| `sim/tb_sha256_core.v` — testbench | **green** (Icarus Verilog) |
| double-hash nonce scanner + UART host link | not written yet |
| synthesis / bitstream / on-board run | not attempted |

Nothing here has run on a board. Per the project's standing rule, "simulated" and
"synthesised" and "mined a real block" are three different claims and only the first
is currently true.

## The vectors are ours

The testbench does not rely on textbook vectors alone. Cases 2–4 are the exact
compression steps of the 80-byte header this project mined into **height 221** of the
live anchor chain, and case 4's output, byte-reversed, is that block's real hash:

```
00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b
```

If the core were wrong in a single bit, that value could not appear. Vectors are
regenerated from `live/chain-blocks.hex`, so they can never drift from reality.

Reproduce:

```bash
iverilog -g2012 -o sim/tb.vvp rtl/sha256_core.v sim/tb_sha256_core.v
vvp sim/tb.vvp
```

## Honest throughput expectation — corrected

An earlier note in this project estimated 100–300 MH/s for this board. **That was
wrong by roughly a factor of 50** and is corrected here rather than quietly dropped.

The XC7A35T has ~20,800 LUTs. A Bitcoin nonce costs two SHA-256 compressions (the
host precomputes the midstate over the header's first 64 bytes, so only the second
block and the outer hash are on-chip):

| design | LUT/core | cycles/nonce | cores that fit | MH/s @100 MHz |
|---|---|---|---|---|
| iterative, 1 round/cycle | ~2,600 | 132 | 6 | ~4.5 |
| unrolled ×2 | ~4,200 | 68 | 3 | ~4.4 |
| unrolled ×4 | ~7,000 | 36 | 2 | ~5.6 |

Measured baselines: this laptop's 8-core scanner **4.0 MH/s**; the laboratory VM
**~1.1 MH/s**. So a realistic bitstream lands **around 5 MH/s** — comparable to the
laptop, roughly 5× the VM. Real numbers replace these estimates after synthesis;
these are arithmetic, not measurements.

## What it is actually for, given that

Not brute-force dominance. The value is:

- **Continuous, dedicated mining** at ~2 W instead of a 50 W laptop tied up in
  20-minute bursts. Always-on beats faster-but-occasional for winning anchor races.
- **A real machine-native artifact**: purpose-built silicon participating in the
  chain, which is the kind of thing this portfolio exists to demonstrate.
- An independent third implementation of the consensus hash, after Python and C.

If the goal were only to stop losing races, running the existing CPU miner
continuously would achieve nearly as much — and that comparison is stated because
the FPGA should be chosen for what it uniquely offers, not for a number that was
never true.

## Next

1. `sha256d_miner.v` — sequence two compressions, scan nonces, coarse-filter on
   leading zero words; the host performs the exact target check (authority stays
   with the tested software path).
2. UART command/report link; host driver via pyserial.
3. Vivado project + XDC for the Cmod A7-35T, then measure.
