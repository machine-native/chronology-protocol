# Experiment 1 — a block moves between two computers by radio

The last untested claim in this repository. `RADIO-RELAY.md` says the driver was
*"written to the RYLR998 datasheet, not yet run on hardware"*, and that line comes
off only when a real block has crossed a real radio link.

## What this is designed to prove, and how the design earns it

The weak version of this experiment is "we sent a file between two machines that
have radios attached". A sceptic answers: how do you know it did not go over the
network, or was not already on the receiver?

Asserting otherwise is not evidence. So the design makes the objection
**physically impossible** instead:

> **The block is mined AFTER the receiver is already air-gapped.**

If the receiving machine has had no network since time T, and the block is mined
at T+20 minutes, then that block **did not exist anywhere in the world** when the
receiver lost its connection. It cannot have been pre-staged, cached or synced.
The radio is the only remaining channel.

That single ordering choice collapses the whole class of "maybe it arrived some
other way" objections, and it costs nothing — the mining capability is already
built and exercised.

## Topology

One radio per machine, so **one USB-A port each**. The two-ports-on-one-machine
requirement in the older runbook was for running both radios on a single box, and
does not apply here.

    LAPTOP (this machine)          CoreX (mini PC)
    transmitter                    receiver
    CP2102 + RYLR998               CP2102 + RYLR998
    online, mines the block        AIR-GAPPED throughout

The laptop is the mobile end, so it carries the radio to distance. The CoreX
stays put and stays offline.

---

## Phase 0 — before anything is plugged in

**Measure the rail. This is the step with no undo.**

`+5V` and `3V3` are adjacent pins on the CP2102 header. 5 V destroys an RYLR998
and there is no spare. Count from the `DTR` end, and measure with the module
**not yet attached**:

- black probe on `GND`, red on `3V3`
- expect **3.2–3.4 V**
- if it reads ~5 V you are on the wrong pin. Stop and recount.

Do this on **both** machines' adapters. Record both readings.

## Phase 1 — wire each radio

Four female-to-female jumpers. Both boards have male pins pre-soldered.

    CP2102    DTR · RXD · TXD · +5V · GND · 3V3
    RYLR998   GND · TXD · RXD · RST · VDD

```
CP2102  GND   ──►  RYLR998  GND
CP2102  3V3   ──►  RYLR998  VDD     3V3, NOT the +5V pin beside it
CP2102  TXD   ──►  RYLR998  RXD
CP2102  RXD   ──►  RYLR998  TXD
                   RYLR998  RST     leave unconnected
```

The spring antenna is already fitted, so there is no risk of transmitting into an
open port.

**Photograph both wired assemblies before powering them.**

## Phase 2 — find the ports and ask each module what it is

On each machine:

```powershell
python -c "import serial.tools.list_ports as l; [print(p.device, p.description, p.hwid) for p in l.comports()]"
```

The CP210x driver may be needed; Windows does not ship it:
`https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers` →
**CP210x Universal Windows Driver**.

Then:

```powershell
python scripts\lora_relay.py probe --port COM<n>
```

`probe` prints the module's raw replies rather than interpreting them, which is
deliberate. **If it disagrees with anything written here, believe the module.**

## Phase 3 — configure both, then re-probe

India: **865–867 MHz is licence-exempt** at these power levels. No amateur
licence is required.

```powershell
# transmitter (laptop)
python scripts\lora_relay.py config --port COM<n> --address 1 --network 18 --band 866000000

# receiver (CoreX)
python scripts\lora_relay.py config --port COM<n> --address 2 --network 18 --band 866000000
```

Same network, same band, **different addresses**. Then run `probe` again on both:
the module is the authority on its own settings, not the command that was typed.

## Phase 4 — link check at close range, with a block that does not matter

Before anything is air-gapped or mined, prove the radios talk. Put both machines
on the same desk. Receiver first, always — a transmission with nobody listening
is simply lost.

```powershell
# CoreX
python scripts\lora_relay.py receive --port COM<n> --out live\radio-linktest --seconds 300

# laptop
python scripts\lora_relay.py send --port COM<n> --block live\pm2-bind-work\..\mine\finalize.json
```

Any existing block works here; it is a link test, not evidence. Record the
**RSSI and SNR** the receiver reports — that is the first real measurement of
this link.

If nothing arrives, work the causes in likelihood order rather than theorising:
wrong port, wrong baud (`--baud 9600`), TX/RX crossed, not powered. Swapping TX
and RX costs nothing and is the most common mistake. If the list runs out, the
logic analyser settles what argument cannot: clip channel 0 to the CP2102's TXD
line, ground to ground, capture at 115200. Bytes leaving the adapter means the
fault is downstream; no bytes means the port or the driver.

---

## Phase 5 — the recorded experiment

**5a. Air-gap the receiver, and prove it.**

On the CoreX: WiFi off, ethernet unplugged. Then capture evidence, because "we
turned it off" is a claim and a command output is a record:

```powershell
Get-Date -Format o
ipconfig /all              # no active adapter with a gateway
ping -n 2 1.1.1.1          # must fail
Get-ChildItem live\radio-received   # must not exist, or be empty
```

**Note the timestamp.** Everything after this depends on it.

**5b. Move the transmitter to distance.**

Carry the laptop as far as the building allows, ideally with at least one solid
wall between. **Record the distance in metres and what is between them.**

**5c. Mine a block that cannot pre-exist.**

VM mining paused. On the laptop:

```powershell
python live\fetch_tip_context.py bitcoin.bitcoin-lab.org 18026
PAYLOAD_HEX=$(cat live\pm2-bind-work\payload.hex) CORES=16 bash live/race.sh
```

At difficulty 1 each full nonce sweep succeeds with probability 1 − 1/e ≈ 63 %,
so one to three rounds of about 20 minutes is normal. **This block is now newer
than the receiver's isolation**, which is the whole point.

**5d. Transmit.**

Receiver first:

```powershell
# CoreX, still offline
python scripts\lora_relay.py receive --port COM<n> --out live\radio-received --seconds 900
```

```powershell
# laptop
python scripts\lora_relay.py send --port COM<n> --block live\mine\finalize.json --repeat 3
```

A 306-byte block becomes **three fragments**: the AT interface caps a send at 240
ASCII characters, hex encoding halves that to 120 binary bytes, and an 11-byte
CHRB header leaves 109 bytes of block per fragment. There is no back-channel, so
`--repeat 3` buys redundancy by repetition rather than by acknowledgement.

**5e. The receiver validates alone.**

It checks proof-of-work locally on every reassembled block and **never trusts the
transmitter for a single byte**. Anything failing is dropped and the fragment set
stays open. Still no network at this point.

**5f. Only now, reconnect and cross-check.**

Bring the CoreX back online and let it fetch the chain **itself**:

```powershell
python live\fetch_tip_context.py bitcoin.bitcoin-lab.org 18026
```

The received block's hash must match what the chain reports at that height. That
comparison uses no code of ours on the transmitting side.

---

## What to capture

| evidence | why it matters |
|---|---|
| measured 3V3 on both adapters | the irreversible step, recorded before it was taken |
| photographs of both wired assemblies | the configuration cannot be recovered afterwards |
| `probe` output before **and** after config | the module's own account of its settings |
| air-gap proof with timestamp | turns "we disconnected it" into a record |
| mining log with timestamps | establishes the block is newer than the isolation |
| transmit log | fragment count, repeats |
| receive log with **RSSI and SNR** | the only direct evidence of an RF path |
| received block file and its SHA-256 | the artifact itself |
| local proof-of-work validation output | the receiver's independent judgement |
| chain cross-check from the receiver | agreement with a party that was never on the link |
| distance in metres, and the walls between | what the link actually achieved |

## What this will and will not establish

**Will:** that the driver works on real hardware; that a self-authenticating
block survives fragmentation, radio transport and reassembly; that a receiver can
validate it with no network and no trust in the sender; and that the block
reached a machine which could not have obtained it any other way.

**Will not:** that LoRa is a practical distribution channel at scale. Three
fragments for 306 bytes, a duty-cycled band and no back-channel are what they
are. The claim is that it works and is verifiable, not that it is efficient.
