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
| MMCM + parallel cores | **built and measured 2026-08-22: 3.59 MH/s** |
| on-board run (selftest) | **PASS on hardware 2026-08-22**, 10^6-nonce scan |
| measured throughput | **3.5911 MH/s** at 8 cores / 60 MHz (was 0.0906 single-core) |
| `mine` mode | not written: needs chain-tip fetch, coinbase build, submission |

Per the project's standing rule, "simulated", "synthesised", "ran on a board" and
"mined a real block" are four different claims. The first three are now true. **The
fourth is not**, and nothing here should be read as saying otherwise.

### Ran on real silicon — 2026-08-22

```
DONE pin        1
ping            link OK
selftest        PASS
  nonce         2757362010
  hash          00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b
```

That nonce and that hash are **height 221 of the live anchor chain** — a block this
project mined in software, now reproduced by an FPGA it also built. A third independent
implementation of the consensus hash, after Python and C, and the first in hardware.

The first run scanned only 4 nonces, which proves the hash and the link but hardly
exercises the scanner. A deep run followed the same day:

```
scanned         1,000,000 nonces      999,999 correctly rejected
stopped on      2757362010            the right one, first time
elapsed         11.03 s
measured rate   0.0906 MH/s
2^32 sweep      13.2 hours
```

**The estimate held.** Predicted 0.091 MH/s and 13 hours; measured 0.0906 and 13.2 — a
0.4% gap. Worth stating precisely because the two earlier estimates for this board were
wrong by 50× and by 8×, and a third guess deserved no benefit of the doubt until a
board settled it.

Better still, 12 MHz ÷ 132 cycles/nonce gives a ceiling of 0.0909 MH/s, so the board is
running at **99.7% of what its cycle count allows**. The UART, the host round-trip and
the reporting path together cost 0.3%. That is the useful result: the 132-cycle model is
confirmed exactly, there is no hidden stall, and the projections below now rest on a
measured constant rather than an assumed one.

What this still does **not** establish, stated because the run is flattering and that is
when the bar should go up:

- **No block has been mined by this board.** `mine` mode is not written.
- The scan ran against a **known answer**. It proves the scanner walks a range and stops
  correctly; it is not a live race against other miners.
- 0.0906 MH/s is **44× slower than this laptop**. Nothing here is competitive yet.

### Bring-up fault, found 2026-08-22: the UART port directions were inverted

The FPGA receives on **J17** and transmits on **J18**; it had been built the other way
round. Such a board synthesises, meets timing, passes DRC, configures, and blinks — and
is silent in both directions with no error reported anywhere.

The **pin numbers were correct all along** and matched Digilent's master XDC exactly
(J18 = `uart_rxd_out`, J17 = `uart_txd_in`). What was wrong was the **directions**.
Digilent's names are relative to the host/USB side: `uart_txd_in` is data the host
transmits *into* the board, so it is an FPGA **input**, and it had been declared an
output.

That has a consequence worth stating plainly: for as long as that bitstream was loaded,
**the FPGA was driving J17 against the FT2232's own output** — two push-pull CMOS
drivers fighting on one net.

Inverted directions was the **first** hypothesis raised during bring-up. It was
abandoned on the strength of a single web search that asserted the opposite, and the
abandonment was reported as though the code had been verified. It had not; one source
had been consulted and believed. Three further theories were pursued before an
instrument settled the question — and the first instinct turned out to be right.

What was **observed rather than assumed**, in the order it arrived:

```
DONE pin                 1            device configured
DRC                      0 checks     fully routed, clean
setup slack (WNS)      +69.588 ns     enormous margin
hold slack  (WHS)       +0.024 ns     normal and met
bonded IOBs              5            clk, both UART pins, both LEDs
heartbeat LED            blinking     bitstream running, 12 MHz clock confirmed
serial at 115200         silent
serial at 6 other rates  silent       so not a baud mismatch
COM port                 opens        so the bridge enumerates
both pins, static level  read HIGH    no information: see below
J17, host transmitting   EDGES        <- traffic arrives here
J18, host transmitting   static       <- so this is the FPGA's transmit pin
```

The heartbeat retired "the bitstream is not loaded", which had been the leading theory
and was wrong. A blinking heartbeat also confirms `CLK_HZ` matches the crystal, which
retires the baud-divisor theory independently of the baud sweep.

Only the last two lines resolved it, and they took two attempts.

Note what the probe deliberately does **not** ask. Inverted directions and swapped pin
numbers are two independent faults with one identical symptom, and no reading of a
datasheet separates them. The probe sidesteps both by asking a question with a physical
answer: *which package pin carries the host's traffic?* Whichever pin moves is the
FPGA's receive pin, and it makes no difference what the net is named or which fault put
it there.

`rtl/pinprobe.v` settles it by measurement. Its first version compared **static
levels** — weak internal pulldowns, on the theory that the bridge's transmit pin idles
actively high and wins, while its receive pin is undriven and loses. On hardware **both
pins read high**, which is no answer at all: a weak internal pulldown cannot outvote a
board pull-up resistor, and UART lines commonly have them. The measurement was simply
too weak for the question.

The current version measures **motion instead of level**. While the host transmits
continuously, the bridge's transmit pin toggles; its receive pin is an input on the
bridge's side and stays still, whatever DC level a resistor parks it at. A pull-up
cannot fake an edge. Both pins remain inputs and neither is ever driven, so it is still
safe to run without knowing the answer.

```bash
vivado -mode batch -source build_pinprobe.tcl        # builds and programs
python ../scripts/fpga_diag.py --port COM4 --stream  # then, in a second window
```

Watch the LEDs while the stream runs: **fast flicker = edges seen on that pin**, slow
blink = static. Every state blinks, so a dark board still unambiguously means "no
bitstream" and can never be misread as a measurement.

Simulation earned its keep here. `sim/tb_pinprobe.v` immediately caught a bug that would
have produced the same useless "both fast" reading as the static version: the
synchronisers power up at zero, so a pin sitting high — every idle UART line — presents
a phantom 0→1 transition on the first samples. A short startup blanking interval
discards it. The static probe shipped without a testbench and cost a hardware cycle;
this one did not.

The port names are now `uart_rx_from_host` and `uart_tx_to_host`, which state their own
direction and cannot be misread the way the vendor's names were.
`tests/test_fpga_constraints.py` pins the mapping, because **this fact cannot be
re-derived by reading** — only by measuring — and a future tidy-up toward the vendor's
names would silently reintroduce a board that builds cleanly and does nothing.

#### What this cost, and why it is written down

Four theories were advanced. Three were wrong — an erased volatile bitstream, a baud
mismatch, and a static-level probe too weak to tell a driven pin from one held high by a
resistor. The **fourth was right and was discarded first**: inverted directions was the
opening hypothesis, dropped because one web search said otherwise, and that dismissal
was written up as if the code had been checked rather than merely googled. Each cycle
cost a build, a program and an observation on real hardware.

What ended it was not a better theory but three instruments that each split one question
into two answerable halves:

| instrument | separates |
|---|---|
| heartbeat LED | "no bitstream" from "no link" |
| `scripts/fpga_diag.py` | "wrong baud" from "total silence" |
| `rtl/pinprobe.v` | "which physical pin carries the traffic" from every naming argument |

Three lessons recorded for next time:

1. **When two candidate causes produce an identical symptom, no amount of reading
   resolves them.** Build the thing that makes them look different.
2. **Simulate the instrument before trusting it.** The static probe shipped without a
   testbench and returned a useless "both fast"; the activity probe's testbench caught
   the equivalent bug in two seconds, before it reached a board.
3. **One source consulted is not a verification.** Saying a hypothesis was "checked
   against the documentation" when a single search result was read and believed is a
   stronger claim than the evidence supported — and here it retired the correct answer
   for three cycles.

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

The top-level testbench needs `-DNO_MMCM`, which swaps the Xilinx clocking primitive
for the input clock directly — Icarus cannot elaborate `MMCME2_BASE`. The logic under
test is identical; only the timebase changes.

```bash
iverilog -g2012 -DNO_MMCM -o sim/top.vvp sim/tb_miner_top.v     rtl/miner_top.v rtl/uart.v rtl/sha256d_miner.v rtl/sha256_core.v
vvp sim/top.vvp
```

## Measured after synthesis — the estimate was wrong twice over

Vivado has now built it (`timing.rpt`, `utilisation.rpt`, `drc.rpt` in this folder,
regenerated 2026-08-22 with the heartbeat included). Timing closes comfortably:
**setup slack +69.588 ns, hold +0.024 ns, zero failing endpoints, zero DRC violations.**

```
LUTs           1,615 of 20,800   (7.8% — smaller than the 2,600 estimated)
registers      3,224 of 41,600   (7.8%)
bonded IOBs        5             clk, two UART pins, two LEDs
critical path  13.08 ns          ->  fmax roughly 76 MHz
clocking       no MMCM/PLL — running straight off the board oscillator
```

> Read setup and hold as two separate numbers. An earlier version of `build.tcl`
> printed the single worst slack across both and reported **0.024 ns** for this build,
> which reads as alarmingly marginal; the real setup margin is **69.588 ns** and the
> 0.024 is a hold path, where small positive slack is normal. One number answering two
> questions is how a healthy build gets mistaken for a broken one.

That last line is the problem, and it is mine. **The Cmod A7's oscillator is 12 MHz**,
while the earlier estimate below assumed 100 MHz and never said so. At 132 cycles per
nonce — a figure hardware has now confirmed to within 0.3%:

| configuration | MH/s | vs this laptop (4.0 MH/s measured) |
|---|---|---|
| 12 MHz, 1 core | **0.0906 measured** | **44× slower** |
| **60 MHz MMCM, 8 cores** | **3.5911 measured** | **0.90× — near parity** |
| ~~75 MHz, 9 cores~~ | ~~5.11~~ | **impossible: measured fmax is 70.4 MHz** |

Both surviving rows are measurements. The third was the original target and is now
ruled out by the hardware itself — worth leaving struck through rather than deleted,
since it was quoted as the plan for two days.

A full 2³² nonce sweep as built takes **13.2 hours**, measured. It cannot compete for a block, and
saying otherwise would repeat the error this section already exists to correct.

The good news is that the path to the ~5 MH/s figure is now *measured* rather than
guessed: the core is smaller than estimated so **9 fit** instead of 6, and timing has
enough slack for a 6× clock multiplier.

**Both are now written and simulated** — an MMCM and an interleaved core array — but
neither has been built or measured, so every number for them below remains a projection.

## Scaling up: MMCM and a parallel core array

Two changes, both parameterised so the configuration is a build argument rather than an
RTL edit:

```bash
vivado -mode batch -source build.tcl -tclargs 8 60    # 8 cores at 60 MHz (default)
vivado -mode batch -source build.tcl -tclargs 9 75    # the aggressive target
```

**The clock.** An MMCM multiplies the board's 12 MHz through a fixed 600 MHz VCO and
divides back down, so the requested frequency must divide 600 exactly — the build script
refuses anything else rather than letting the MMCM silently synthesise something other
than `CLK_HZ`, which would corrupt the baud divisor and the heartbeat together. Reset is
held until the MMCM reports lock, since running logic on a frequency that is still
settling corrupts state in ways that then look like logic bugs.

**The cores.** `NUM_CORES` scanners run in parallel, **interleaved**: core *i* starts at
`nonce_start + i` and strides by `NUM_CORES`, so between them they cover every nonce
exactly once with no shared state and no coordination during the search.

Interleaving rather than slicing the range into contiguous blocks is deliberate, and the
reason is measurement honesty. With slicing, an answer *D* nonces ahead is found by one
core while the rest grind through unrelated regions — so wall-clock tracks a **single
core's** rate while appearing to measure the whole array. Interleaved, reaching that
answer takes *D / (N × per-core rate)*, which is what aggregate throughput should mean.

Two cores can report in the same cycle, since they scan disjoint nonces and both
candidates are genuine. The lowest index wins; the other is dropped. That costs nothing
real — the host re-checks every reported nonce against the exact target anyway, and a
dropped candidate at difficulty 1 is a retry, not a lost block.

### Built and measured, 2026-08-22

```
config          8 cores at 60 MHz
setup slack     +2.468 ns   -> critical path 14.199 ns -> fmax 70.4 MHz
hold slack      +0.020 ns   met
scanned         5,000,000 nonces in 1.39 s
measured        3.5911 MH/s      (projected 3.64 -- 98.7%)
2^32 sweep      0.3 hours        (was 13.2)
```

**39.6× faster than the single-core build**, and 90% of this laptop's measured
4.0 MH/s — near parity, not past it.

**The 75 MHz target is dead.** Measured fmax with 8 cores is 70.4 MHz; 75 MHz needs a
13.33 ns path and this one is 14.199 ns. The original 5.11 MH/s projection assumed
9 cores at 75 MHz and **that configuration cannot close on this part**. Filling the
fabric cost roughly 6 MHz against the single-core build's ~76 MHz, which is the ordinary
price of congestion and was not accounted for.

More cores at 60 MHz remains open, and is now the only route left:

| configuration | projected MH/s | status |
|---|---|---|
| 8 cores at 60 MHz | 3.64 | **measured 3.5911** |
| 12 cores at 60 MHz | 5.45 | untested; timing may not hold |
| 16 cores at 60 MHz | 7.27 | untested; likely too congested |
| ~~9 cores at 75 MHz~~ | ~~5.11~~ | **ruled out — fmax is 70.4 MHz** |

Every projection here scales 132 cycles per nonce per core, a constant hardware has
confirmed twice: to 0.3% single-core and 1.3% across eight. That is arithmetic on a
measured quantity, which is the only reason it is worth printing — and it stays a
projection until a board returns a number.

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
2757362010 and that block's hash. **It passed on 2026-08-22.**

Run it deep to exercise the scanner and measure the real rate:

```bash
python ../scripts/fpga_host.py selftest --port COM4 --depth 1000000
```

A deep scan spends many seconds with neither side transmitting, and on 2026-08-22 that
killed the link outright: `ClearCommError ... Access is denied` after a ping had
succeeded moments before — Windows suspending an idle FTDI out from under an open
handle. The host now sends a ping every second during a long scan to keep the link warm,
and prints elapsed time so a long run shows a sign of life.

That keepalive is only safe if a `'P'` arriving mid-scan neither aborts the scan nor
corrupts the report, so `sim/tb_miner_top.v` checks exactly that rather than assuming
it: the ping is answered, and the 37-byte report still arrives intact. If the link dies
anyway, the host now says so explicitly instead of raising a traceback — a lost port is
not a mining failure, and the two should never look alike.

`mine` mode was locked until selftest passed, because wiring live anchoring to a miner
that had never returned a known-correct answer would be the kind of shortcut this
project does not take. That precondition is now met; the mode is simply not written
yet — it needs chain-tip fetch, coinbase construction and submission.

## Wire protocol

```
host -> FPGA   'W' + midstate[32] + tail[12] + nonce_start[4]   (big-endian) — start
host -> FPGA   'S'   abort            'P'   ping
FPGA -> host   'F' + nonce[4] + digest[32]   candidate (host applies the real target)
FPGA -> host   'E'                            range exhausted
```
