# Redactions in the live records

Recorded 14 September 2026. Each file below had a string that identified the operator's
machine, network or location — a local filesystem path, a host name, a machine name, an
adapter model, a private or public network address, or a country — replaced by a
placeholder in angle brackets or by a neutral description. Nothing else in those files
changed: not a hash, not a timestamp, not a measurement, not a verdict. The placeholders
are `<repo>` (the working copy of this repository), `<nanoproof-air>` (the sibling
checkout), `<receiver-host>`, `<host>`, `<home>` (the user directory of the build
machine), `<private-ipv4>`, `<lan-ipv4>` and `<public-ipv4>`; the machine name of the
radio receiver reads "the receiver (a small-form-factor PC)", and the country of the
second seed's provider reads "a second provider in another country".

Two of these files are named by digest in `live/MANIFEST-live.sha256` and one in
`live/anchor-evidence/ACCEPTANCE.md`. Those digests are the digests of the files **as
captured**, and they are left as written: a manifest that is regenerated after the fact
stops being a record of the capture. The digests of the redacted copies are given here, and
`MANIFEST.sha256` at the repository root lists the redacted copies, so a clone verifies.

| file | what was replaced | sha256 as captured | sha256 after redaction |
|---|---|---|---|
| `live/node-evidence/debug.log` | local filesystem path, a private address and the public IPv4 address echoed by an IRC server | `aadc1576c8e5ad2e599bacefdb7cde49576a4aee9d2e44df1c5a337f48f3b302` | `9113e835229d31177c1380632dc3d85fa98aff585f17eb838d131519dd947b26` |
| `live/node-evidence/sandwich-debug.log` | local filesystem path, a private address and the public IPv4 address echoed by an IRC server | `4073afdfb0ff4b30f114a42a55e1b415a66e4f33c6b29bdbe950996c9a38e56b` | `8aa0e6d0b3fa912e677c2eb1125a977c81ca553288b8abc2e7e33fe8121ab6be` |
| `live/anchor-evidence/finalize-height221.json` | local filesystem path | `e9133e1e76914787fff43f3a9de7dd20c8e4b7adbb30c0ec08e226ab2920973e` | `10651a29f900bd27f00c88d471a75277b7d10ce12d444ada1c83951e706a42fe` |
| `reports/mined-block.json` | local filesystem path | `7b046db18a4bb3ce281f62bfd97ddb1c9b740c1c9081a6478de8aed9bfd86b34` | `7f7ebf22ab71ffbf6dc8379e2a35c3a0513f281a9928a0bf49ab6dda26c0d2a8` |
| `live/pm-bind-work/challenge.json` | local filesystem path | `f22c0c7ebd11e33c50be303b16232b47d54b1b26c5de41b6bf20ede3d39ba9d3` | `6383c5f29e4aac76a8948c968a3d2106d0c019c8ded17a7319a43b349e3f251d` |
| `live/pm2-bind-work/challenge.json` | local filesystem path | `ed1e6ac7c637afc3a1cf40aedd2b12f12a8e71207fec3e6f68fab9efa9fcab05` | `a4131d5b9fa7c190482c3dd951aa2d574f2d85b85937096401c13639bbbaa7ef` |
| `live/lora-experiment/01-rail-measurements.json` | the receiver's machine name | `2549ed17152edadddf8b0fb854c9bcd7592a5c5c0c968d4ac6cafd222fdbdee3` | `9c9d640ab10c7669055ec1761c54902d34ee0a9f86419017b16c22c1758c8fb4` |
| `live/lora-experiment/02-transmitter-config.json` | the country named in the band finding (the band, 865–867 MHz, and the finding are unchanged) | `b9d36ff5dc1c428b5b596a2bd09bc451c16aefd54a03a1fbad5d178ade7a36f6` | `40633d99f4540053d80189eb753eb5181e99d0e532e4b97979408d6089099899` |
| `live/lora-experiment/03-receiver-config.json` | the receiver's machine name (twice) and the country named in the band finding | `6e9219391d81c639edb74a958be13856761333444779a9c9ab6320102e4f8693` | `8511a1ab2c316271124af1342d852cccc8ade3d5a8eb14de1abe793ecff22628` |
| `live/lora-experiment/04-link-check.json` | the receiver's machine name | `ff4a3e25dd124cdb6a4676520c980ee917b681cd09bda84083c0f70491631819` | `78a91b38b22e5ec2521d2fdcf066ef666cb52927931d7fce256005b67319ffeb` |
| `live/lora-experiment/05-receiver-isolation.json` | host name, adapter models, two private addresses and the receiver's machine name | `438e454a7dd9cae979a200e367fc94b8ef57a13d0984674f2c9f70e2d63578dd` | `b950cefbe62477ec269bc0758a2edd002b157da196391deb7682230d732cddda` |
| `live/lora-experiment/08-cross-check.json` | a private LAN address | `29c6c557ad619b7ee5cf6d60ab47bd3df91dec209e40317a36588ed6c84f2eb0` | `ff99c4c879186d52fa79bae3f54584e2e66bce9715e590e0ccbc15ef69e68e4d` |
| `live/lora-experiment/09-block-extended.json` | the receiver's machine name | `957537a7e4ee7fb3893a6fe90cabf7741abeb43385eb03b35eba5a6a70f8d009` | `872c0734605f3c472da892ced185e3ded241bc2ce81b2988482eb3a9cfeb2c70` |
| `live/d2-seed-2.json` | the country of the second seed's provider (the provider name, the public address and the SSH host-key fingerprint of the public server are unchanged) | `7dcd4daa9e5f4d7348608b2a98c8aa89e75954f8338a20b070c39348aa3943ba` | `e1913c0c6bd74f38fb4224790d5cbce0b8339a241769788c0819752f064cb62d` |
| `fpga/drc.rpt` | host name in the Vivado report header, and the user directory in the `Command` line | `c12c05f3b89032e16d037830f9ae13b4618c475ce20a58ea87fbc8f65aaf424d` | `ff6ca5763a5e20868ccfcaadaef7f88a2c5fcfa3b88425e7222e7c83738783cb` |
| `fpga/timing.rpt` | host name in the Vivado report header, and the user directory in the `Command` line | `cbcdeb55a6dad81cbff186f906f937fe0b2fe5914a60a17b9ed77cc836d6e8a1` | `a9101091f619b1e96ccd569643470870fcf1758b054cd76ac2a908965b018e1e` |
| `fpga/utilisation.rpt` | host name in the Vivado report header, and the user directory in the `Command` line | `33ec3c2a6f5b485acc880362965c1ea221b2ee041d970e9025615fca84332b10` | `18fdb0d03e348a46bd2401abc43717061a1a362494f6970db38fe8b2f365dd1a` |

The Vivado reports under `fpga/` are tool output; only the `Host` line and the user
directory in the `Command` line of their headers changed. The two binding scripts under
`scripts/` carried absolute paths to sibling checkouts; they now take a sibling directory
by default and an environment variable otherwise.

The same machine name and country appeared in documents that are not records —
`docs/LORA-EXPERIMENT-RUNBOOK.md`, `docs/RADIO-RELAY.md`, `docs/D2-SECOND-SEED-RUNBOOK.md`
and `scripts/lora_relay.py` — and were replaced there in the same way; those files carry
no capture digest and are not tabulated.

The two debug logs and `fpga/timing.rpt` use CRLF line endings, as the programs that
wrote them did; the redaction preserved that, and the line count of each is unchanged.

## Later amendments to files listed above

A digest in the right-hand column is what the redaction produced on 14 September 2026.
It is not a promise that the file has never changed since. Where one has, it is listed
here so the chain of digests stays followable; `MANIFEST.sha256` at the repository root
always lists the current copy.

| file | change | sha256 after redaction | sha256 now |
|---|---|---|---|
| `live/lora-experiment/01-rail-measurements.json` | 2026-09-27: the instrument was identified. `"handheld multimeter"` became the make, model, count and category, with a block recording that the identification came from photographs taken three weeks after the measurement and was confirmed by the operator. **No reading, verdict or timestamp changed.** | `9c9d640ab10c7669055ec1761c54902d34ee0a9f86419017b16c22c1758c8fb4` | `51ede2f61e70d0708e445003f7b6bebfa3a2f9bffe66a195b6a38e6a6e2120e6` |
| `reports/mined-block.json` | 2026-10-01: replaced by the receipt for the epoch-8 anchor (block 1270), whose `template` field held a local filesystem path when captured (sha256 `ada14d074875367f80a59709572e5bb88231a7c97afd62c57b37190fd43ebddb`); it was replaced by `<repo>` before commit, and `scripts/finalize_mined_block.py` now writes the path relative to the working copy, so the next receipt needs no redaction. **No hash, nonce or status changed.** | `7f7ebf22ab71ffbf6dc8379e2a35c3a0513f281a9928a0bf49ab6dda26c0d2a8` | `8b76e1d44bc7060208da7dcc4cb820fcfd7817d0ca97c5e494adc585074faa7a` |
