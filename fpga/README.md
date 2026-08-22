# FPGA miner — Cmod A7-35T (work in progress)

A SHA-256d miner in hardware for the anchor chain: our own silicon mining our own
chain. Started 2026-08-21.

## Status

| piece | state |
|---|---|
| `rtl/sha256_core.v` — compression core, 1 round/cycle | **simulated, all vectors pass** |
| `sim/tb_sha256_core.v` — testbench | **green** (Icarus Verilog) |
| `rtl/sha256d_miner.v` — double-hash nonce scanner | **simulated: finds real chain nonces** |
| `rtl/uart.v` + `rtl/miner_top.v` — UART link | **simulated end-to-end** |
| `scripts/fpga_host.py` — host driver | written; midstate matches RTL |
| `build.tcl` + `constraints/cmod_a7.xdc` | ready to run |
| synthesis + bitstream | **DONE 2026-08-22 — timing met, reports in this folder** |
| on-board run (selftest) | **blocked — programmed board does not answer over UART** |

Nothing here has run on a board. Per the project's standing rule, "simulated" and
"synthesised" and "mined a real block" are three different claims and only the first
is currently true.

**Open bring-up fault (2026-08-22).** A board reported as programmed returns nothing to
`ping`. Every remotely checkable cause has been eliminated: the UART pin directions
match Digilent's convention (`uart_rxd_out` is an FPGA *input*), the pin assignments and
the 12 MHz clock pin match the board's master constraints, the baud divisor is
104 for a 0.16% error, and the end-to-end simulation drives real UART bytes through the
top level and passes. The design has met timing but has never been observed running.

Two instruments were added rather than continuing to guess: a **1 Hz heartbeat LED**,
which separates "no bitstream" from "no link", and **`scripts/fpga_diag.py`**, which
separates "wrong baud" from "silence". Both are described under bring-up below.

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

## Measured after synthesis — the estimate was wrong twice over

Vivado has now built it (`timing.rpt`, `utilisation.rpt` in this folder). Timing closes
comfortably: **WNS +70.246 ns, zero failing endpoints, all constraints met.**

> These two reports are from the build of 2026-08-22 and **predate the heartbeat
> counter**, which adds roughly 32 flip-flops and a comparator. The figures below are
> therefore very slightly low rather than wrong, and are left as measured instead of
> being adjusted by arithmetic. They will be replaced by the next build's own output.

```
LUTs           1,593 of 20,800   (7.7% — smaller than the 2,600 estimated)
registers      3,200 of 41,600   (7.7%)
critical path  13.08 ns          ->  fmax roughly 76 MHz
clocking       no MMCM/PLL — running straight off the board oscillator
```

That last line is the problem, and it is mine. **The Cmod A7's oscillator is 12 MHz**,
while the earlier estimate below assumed 100 MHz and never said so. At 132 cycles per
nonce:

| configuration | MH/s | vs this laptop (4.0 MH/s measured) |
|---|---|---|
| **as built** — 12 MHz, 1 core | **0.091** | **44× slower** |
| + MMCM at 75 MHz, 1 core | 0.57 | 7× slower |
| + MMCM at 75 MHz, 9 cores | 5.11 | slightly faster |

A full 2³² nonce sweep as built takes **13 hours**. It cannot compete for a block, and
saying otherwise would repeat the error this section already exists to correct.

The good news is that the path to the ~5 MH/s figure is now *measured* rather than
guessed: the core is smaller than estimated so **9 fit** instead of 6, and timing has
enough slack for a 6× clock multiplier. Both are ordinary additions — an MMCM primitive
and a parallel instantiation with a nonce-range splitter — neither yet written.

**What the bitstream is for right now is correctness, not speed**: proving that silicon
reproduces a proof-of-work answer this project already established. That is what
`selftest` checks, and it is the milestone that matters.

## Earlier throughput estimate — kept for the record

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

1. ~~`sha256d_miner.v`~~ — **done and simulated.** Given the real height-221 work
   (host-computed midstate + 12-byte tail) and a nonce window bracketing the answer,
   it returns nonce 2757362010 and the chain's own hash; a window stopping short
   exhausts cleanly with no false positive. It coarse-filters on trailing zero words
   only — the host still applies the exact compact target, so hardware narrows the
   search and software decides validity.
2. ~~UART command/report link; host driver~~ — **done and simulated end-to-end.**
   `sim/tb_miner_top.v` drives real UART bytes into the top level and requires
   'F' + nonce 2757362010 + that block's digest to come back out. It does. The host
   driver's midstate computation was cross-checked against the RTL testbench
   constant and matches byte-for-byte.
3. **Build the bitstream** (needs Vivado; see below), then measure the real rate.

Two byte-order traps were hit and are recorded so they are not re-hit: the leading
zeros of a *displayed* block hash are the *trailing* words of the raw digest, and the
nonce is a number here but is stored little-endian in the header, so it must be
byte-swapped on the way into the block. Each bug made the scanner silently find
nothing — the kind of failure only a real known-answer vector catches.


## Building the bitstream

On a machine with Vivado and the Cmod A7-35T:

```bash
cd fpga
vivado -mode batch -source build.tcl        # -> build/miner_top.bit
```

Then check two numbers before believing anything:

- `build/utilisation.rpt` — LUT usage. This determines how many cores could be
  instanced later, and whether the ~5 MH/s estimate was right.
- `build/timing.rpt` — worst negative slack must be **positive**. If it is not, the
  design did not meet timing and any measured rate is meaningless.

Then program it — scripted, so that "was it actually programmed?" is answered by a
readback rather than by remembering what a dialog said:

```bash
vivado -mode batch -source program.tcl      # prints the DONE pin state
```

This also **closes the JTAG session before exiting**, which matters on this board:
JTAG and the UART are two channels of the same FT2232 chip, and an open Hardware
Manager target can hold the serial port shut. Note that programming is **volatile** —
it survives until power is removed, so unplugging the board to hunt for its COM port
erases it.

### Bring-up, in the order that isolates faults

**LED0 blinks once a second** as soon as a working bitstream is loaded, driven off the
clock alone and independent of the UART. Check it before anything else:

- **Blinking** — the bitstream is running and the clock is right. Any remaining fault
  is in the serial path.
- **Dark** — nothing is running. The programming did not take; do not debug the UART.
- **Blinking at visibly the wrong rate** — `CLK_HZ` disagrees with the crystal, which
  is the same error that corrupts the baud divisor and turns the UART to garbage.

That distinction is the whole reason the heartbeat exists. Before it, an unprogrammed
board and a broken link looked identical — both LEDs dark — and bring-up here stalled
on exactly that ambiguity.

```bash
pip install pyserial
python ../scripts/fpga_diag.py                        # which port is the board?
python ../scripts/fpga_diag.py --port COM4            # why is it silent?
python ../scripts/fpga_host.py ping     --port COM4   # link alive?
python ../scripts/fpga_host.py selftest --port COM4   # does it find a KNOWN answer?
```

`fpga_diag.py` exists because a failed `ping` is uninformative on its own: wrong port,
unprogrammed device, wrong baud and dead wiring all produce identical silence. It
enumerates ports and flags the FTDI one, checks the port opens, then sweeps baud rates
to separate "alive but mismatched" from "nothing there."

`selftest` replays the real height-221 work and requires the board to return nonce
2757362010 and that block's hash. **`mine` mode is deliberately locked until
selftest passes** — wiring live anchoring to a miner that has never returned a
known-correct answer would be exactly the kind of shortcut this project does not take.

## Wire protocol

```
host -> FPGA   'W' + midstate[32] + tail[12] + nonce_start[4]   (big-endian) — start
host -> FPGA   'S'   abort            'P'   ping
FPGA -> host   'F' + nonce[4] + digest[32]   candidate (host applies the real target)
FPGA -> host   'E'                            range exhausted
```
