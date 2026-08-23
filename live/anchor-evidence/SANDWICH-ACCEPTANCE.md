# Reality-Sandwich Acceptance Evidence — block C at height 222, 2026-08-19

Compact record for the v0.2.0 sandwich run; the authoritative, self-contained artifact
is `vectors/valid/reality-sandwich-bundle.cbor` (offline verifier:
`scripts/verify_sandwich.py`). Executed 2026-08-19 by parthod0x.

## The sandwich

```
B0   00000000fc80fe4f27b59cafbf782f029f586151bd144115b3d5f1ee360d088b   height 221
       (the v0.1.1 live-anchor block itself)
  ≺  acquisition   2026-08-19 ~11:28-11:29 UTC
       challenge q  6bfc8e3da4f18f8c59fae11bce0e311b1d19bac6ca1bd6e1e1ff77c3205aeb34
       10 real NTPv4 exchanges: time.nist.gov (stratum 1), ptbtime1.ptb.de (stratum 1),
       time.google.com (stratum 1), time.windows.com (stratum 4), time.apple.com
       (stratum 2) — two chained observations per witness, per-exchange nonce derived
       from q embedded in every request's transmit timestamp and echoed by every server
       consensus: CONSENSUS, q=3 of 5, f=1, intersection width ~84 ms
  ≺
C    0000000055cddf6e969747b574d17435af0799c839a3f149e020745b69419fa0   height 222
       nNonce 2885682098, nTime 1787138996, difficulty-1 real work, won on first attempt
       payload: epoch-1 checkpoint (chained to the sealed epoch-0 checkpoint commitment)
  ≺
B1   00000000d237552978a87059c4795268ded8bffe0378dd9066000d3332edafa4   height 223
B2   000000005b168a66d17e1ca3e7b2a633304f838fb78f583930c237f38fb3d914   height 224
       both mined by the laboratory's own VM — a second machine, same operator
```

## Verification

- Final bundle sha256 `24132630527490192b6a06db07cf40cd8522e7ad6a6018bdf36944a662ca7407`,
  verdict **`SANDWICH_PASS`**, all 20 checks true, burial depth 2 at assembly time
  (report: `reports/sandwich-verification.json`).
- Unmodified released v0.1.5 client (sha256 `c3f15fc5…`), fresh datadir
  (`live/node-evidence/sandwich-datadir/`), fed the 224-block chain over the v0.1 wire:
  224/224 `ProcessBlock: ACCEPTED`, log tail
  `new best=00000000fc80fe height=221` → `0000000055cddf height=222` →
  `00000000d23755 height=223` → `000000005b168a height=224`
  (`live/node-evidence/sandwich-debug.log`).

## Limits

Difficulty-1 bounds are mechanical, not economic. NTP is unauthenticated; operator and
path diversity is the mitigation and the profile says so. The window's physical width
is one block cadence per side; nothing inside it is ordered by the sandwich itself.
The ERA field is a model expectation, never evidence. Full non-claims:
`docs/REALITY-SANDWICH.md` §6.
