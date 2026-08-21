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
| fragmentation / reassembly / validation / airtime math | **tested** (7 tests) |
| serial AT driver (`scripts/radio_relay.py`) | written to the RYLR998 datasheet, **not yet run on hardware** |
| an actual over-the-air block transfer | **pending hardware** — the note in the script is removed when it happens |

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
python scripts/radio_relay.py send --port COM7 --tail 5
# end B — listen, validate, append:
python scripts/radio_relay.py recv --port COM8 --out received-blocks.hex
```

Then prove it meant something: check the received file against the chain fetched
over the internet — the hashes must agree, and the receiver never trusted the
transmitter for a single byte.

Airtime for one 306-byte block at SF9/125 kHz is ~1.2 s across 3 fragments, so
even a 1% duty cycle sustains a fresh block every ~2 minutes — far faster than
the chain produces them.
