# Third-party code, data, documents and services

This repository is Apache-2.0 (see `LICENSE`, `NOTICE`, `LICENSING.md`). The items below
are not the project's own. Each is listed with what it is used for, its licence or terms
as read from the source on 14 September 2026, and where to read it. Nothing here is
vendored except where the row says so; the rest is imported, invoked, referenced or
called over the network.

## Software the verifier and tools depend on

| item | used for | licence | source |
|---|---|---|---|
| OpenSSL 3.5+ | ML-DSA-87 and SLH-DSA-SHAKE-256s signatures (`ctp/pq.py`) | Apache-2.0 | https://github.com/openssl/openssl/blob/master/LICENSE.txt |
| pytest | the test suite (`pyproject.toml` extra `test`) | MIT | https://github.com/pytest-dev/pytest/blob/main/LICENSE |
| python-opentimestamps | creating and upgrading `.ots` proofs (`scripts/ots_stamp.py`, `ots_upgrade.py`); reading them needs no package (`ctp/ots.py`) | LGPL-3.0-or-later | https://github.com/opentimestamps/python-opentimestamps/blob/master/LICENSE |
| opentimestamps-client | the reference `ots verify` named in `VERIFY.md` §6 | LGPL-3.0-or-later | https://github.com/opentimestamps/opentimestamps-client/blob/master/LICENSE |
| pyserial | serial access to the LoRa modules and the FPGA (`scripts/lora_relay.py`, `radio_relay.py`, `fpga_host.py`, `fpga_diag.py`; extra `serial`) | BSD-3-Clause | https://github.com/pyserial/pyserial/blob/master/LICENSE.txt |
| piexif | EXIF timestamps of the photographs (`scripts/run_g2b.py`, `run_g6.py`; extra `acquisition`) | MIT | https://github.com/hMatoba/Piexif/blob/master/LICENSE.txt |
| astronomy-engine | the celestial model wrapped by the non-public astrolabe-engine whose prediction is recorded as a labelled expectation (`live/anchor-evidence/astrolabe-expectation.json`) | MIT | https://github.com/cosinekitty/astronomy/blob/master/LICENSE |
| Icarus Verilog | simulating the FPGA RTL (`fpga/sim/`) | GPL-2.0 (tool only; no Icarus code is in this repository) | https://github.com/steveicarus/iverilog/blob/master/COPYING |
| AMD/Xilinx Vivado | synthesis, bitstream and programming (`fpga/*.tcl`); `fpga/*.rpt` are its reports and carry its header | vendor EULA; the tool is not redistributed here | vendor documentation |

## Data and source material carried in or derived into this repository

| item | where | licence | source |
|---|---|---|---|
| Digilent Cmod A7 master XDC | `fpga/constraints/cmod_a7.xdc` is derived from `Cmod-A7-Master.xdc` (pins this design uses, with measured corrections noted in the file) | MIT, Copyright (c) 2017 Digilent | https://github.com/Digilent/digilent-xdc/blob/master/Cmod-A7-Master.xdc · https://github.com/Digilent/digilent-xdc/blob/master/License.txt |
| Cloudflare Roughtime ecosystem snapshot | the long-term keys and addresses pinned in `scripts/run_g5.py` (`ecosystem.json`, fetched 2026-08-21) | Apache-2.0 | https://github.com/cloudflare/roughtime/blob/master/ecosystem.json · https://github.com/cloudflare/roughtime/blob/master/LICENSE |
| trottier/original-bitcoin | the January-2009 block and transaction structure that `ctp/bitcoin_jan09.py` implements (`SOURCES.md`) | MIT, Copyright (c) 2009 Satoshi Nakamoto | https://github.com/trottier/original-bitcoin/blob/master/license.txt |
| original-bitcoin-laboratory/genesis | the derivative chain this protocol anchors into: genesis block, network parameters and patch (`SOURCES.md`); the chain itself is not part of this repository | MIT | https://github.com/original-bitcoin-laboratory/genesis/blob/main/LICENSE |
| Contributor Covenant 2.1 | `CODE_OF_CONDUCT.md`, reproduced with the attribution its text asks for | the covenant's own terms, at its homepage; not restated here | https://www.contributor-covenant.org/version/2/1/code_of_conduct/ |
| IETF Roughtime draft | the wire format `ctp/roughtime.py` implements | IETF document; BCP 78 terms | https://datatracker.ietf.org/doc/draft-ietf-ntp-roughtime/ · https://www.rfc-editor.org/bcp/bcp78 |

`tools/rolling-code.html` carries a minimal SHA-256 routine. The file records no external
origin for it and none is asserted; it is covered by this repository's licence.

## Public services the acquisitions and checks talk to

No terms are asserted for these beyond what each service publishes; they were used as
ordinary clients. None of them is operated by this project.

| service | role | endpoints |
|---|---|---|
| NTP operators | the five NTPv4 witnesses in every sandwich (`scripts/run_sandwich.py`) | `time.nist.gov`, `ptbtime1.ptb.de`, `time.google.com`, `time.windows.com`, `time.apple.com` |
| Roughtime servers | the Ed25519-signed witnesses of epoch 3 (`scripts/run_g5.py`) | `roughtime.cloudflare.com:2003`, `time.txryan.com:2002` |
| OpenTimestamps calendars | aggregation of the `.ots` proofs into Bitcoin (`scripts/ots_stamp.py`) | `a.pool.opentimestamps.org`, `b.pool.opentimestamps.org`, `a.pool.eternitywall.com`, `ots.btc.catallaxy.com` |
| Esplora (blockstream.info) | the explorer `scripts/confirm_attestations.py` asks by default (`--explorer` selects another) | `https://blockstream.info/api` |

## Hardware referenced by the records

Vendor documents only; nothing from them is reproduced here.

| part | role |
|---|---|
| REYAX RYLR998 | the LoRa modules of the radio experiment (`docs/RADIO-RELAY.md`, `live/lora-experiment/`) |
| Silicon Labs CP210x | the USB-to-UART bridge and its driver (`live/lora-experiment/03-receiver-config.json`) |
| Plantower PMS7003 | the particulate sensors of epochs 6 and 7 |
| Bosch BME280 | the humidity, pressure and temperature sensor of epoch 7 |
| Digilent Cmod A7-35T | the FPGA board (`fpga/`) |

URLs above were fetched on 14 September 2026 and returned the pages named; the vendor
product pages for the REYAX and Plantower parts did not answer a scripted fetch that day
and are therefore not linked.
