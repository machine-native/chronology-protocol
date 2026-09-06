# Radio block relay (CHRB v1) — chain distribution without the internet

A 306-byte block does not need the internet. This profile broadcasts anchor-chain
blocks over LoRa (or any byte-oriented radio link) so that receiving the chain
requires nothing but a $15 module and physics.

## Why it can be this simple

A proof-of-work block is **self-authenticating**: its hash must satisfy its own
embedded difficulty target and it must name its parent. So the relay needs

- no encryption — the data is public;
- no transmitter authentication — the work *is* the authentication; forging a
  block costs exactly as much as mining one;
- no handshake or back-channel — the sender repeats its broadcast, and any
  receiver that has heard every fragment once reconstructs and validates locally.

A corrupted or forged transmission simply fails validation and is dropped. The
receiver trusts mathematics, not the sender — the same property the rest of this
project is built on, expressed at 250 bytes per packet.

## Wire format

```
magic   4B   "CHRB"
version 1B   0x01
id      4B   first 4 bytes of dsha256(block header) — demultiplexer, not security
index   1B   fragment number (0-based)
count   1B   fragments in this block
payload      raw block bytes
```

Implementation and the reassembly rules: `ctp/radio.py`. Fully unit-tested,
including out-of-order delivery, duplicates, loss-then-repeat, corruption, and a
forged block without valid work (`tests/test_radio.py`).

## Status, honestly

| layer | status |
|---|---|
| fragmentation / reassembly / validation / airtime math | **tested** (9 tests) |
| serial AT driver (`scripts/lora_relay.py`) | **run on hardware 2026-09-06** — two RYLR998s, firmware V1.2.4 |
| an actual over-the-air block transfer | **DONE 2026-09-06** — block 732 crossed 13.7 m and a cement wall between two machines |

### What was done, 2026-09-06

Block **732**, `00000000001d9678…`, moved from a laptop to a mini PC 45 ft away
through a thick cement wall, a wooden door and a wooden cupboard. 306 bytes as
three fragments (240/240/198 chars), complete on the first pass with no
fragment loss, RSSI −52 to −61 dBm, SNR 8–9 dB.

The receiver validated proof-of-work **locally, with no network**, and never
trusted the transmitter for a byte. The received file is byte-identical to the
transmitted one.

**The ordering is the argument.** The receiver was air-gapped and evidenced at
15:54:06Z; the block was mined at 16:12:05Z. It did not exist anywhere when
that machine lost its network, so it cannot have been pre-staged, cached or
synced. At 16:23:17Z, reconnected, the receiver asked the chain itself and got
the same hash as its tip.

Evidence in `live/lora-experiment/`.

**One gap, stated plainly.** The closing network capture is internally
inconsistent — `ipconfig` showed every adapter disconnected while a ping in the
same block got a LAN reply, meaning the network was already returning. There is
no independent capture of network state between 15:54Z and the block's arrival
at 16:15Z, leaving a three-minute window after the block existed in which a
reconnected machine could in principle have fetched it from the chain instead.
Nothing suggests it did, and the RSSI/SNR of nine fragments from address 1 is
not something a chain fetch produces. But the experiment was designed to make
that objection *impossible* rather than merely implausible, and on this run it
is only implausible. Closing it is a tooling change: `receive` should record the
host's network state itself, at start and finish, inside the isolated session.

### What this does not claim

That LoRa is a practical distribution channel at scale. Three fragments for 306
bytes, a duty-cycled band and no back-channel are what they are. The claim is
that it works, and that a receiver can verify what arrives without trusting the
sender.

## Hardware (~$40 total for both ends)

- 2 × REYAX **RYLR998** (868/915 MHz, AT commands over UART) — or RYLR896.
- 2 × USB-to-UART adapters (CP2102/FT232) if the modules are bare; some sellers
  ship USB versions.
- Antennas are included with the modules. Range: hundreds of metres indoors,
  kilometres line-of-sight at SF9+.

India note: LoRa at **865–867 MHz** is licence-exempt in India (no amateur
licence needed at these power levels), so this profile can run legally without a
ham licence. Set the module band accordingly (`AT+BAND=866000000`). An amateur
licence only becomes relevant for other bands/modes.

## Runbook (once hardware exists)

```bash
pip install pyserial
# end A — broadcast the newest five blocks, repeating within a 1% duty cycle:
python scripts/lora_relay.py send --port COM7 --block live/mine/finalize.json
# end B — listen, validate, append:
python scripts/lora_relay.py receive --port COM8 --out live/radio-received
```

Then prove it meant something: check the received file against the chain fetched
over the internet — the hashes must agree, and the receiver never trusted the
transmitter for a single byte.

Airtime for one 306-byte block at SF9/125 kHz is ~1.2 s across 3 fragments, so
even a 1% duty cycle sustains a fresh block every ~2 minutes — far faster than
the chain produces them.
