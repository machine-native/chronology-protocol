# Source constraints used for v0.1.0

The implementation is designed against the public Original Bitcoin Laboratory derivative chain
and the January-2009 transaction/block structure.

Key externally verified constraints:

- derivative genesis:
  `00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a`
- derivative nBits: `0x1d00ffff`
- derivative network is composed from the v0.1.0 source tree plus declared genesis/network/bootstrap
  substitutions
- January-era `CTransaction::CheckTransaction()` constrains coinbase scriptSig length to 2..100
  bytes
- transaction inputs contain `prevout`, `scriptSig`, `nSequence`
- blocks serialize the six-field 80-byte header followed by transaction vector
- block hash is SHA-256d of the 80-byte header
- the derivative repository publishes a complete raw genesis block; `ctp.bitcoin_jan09` embeds that
  test vector and must reproduce its hash before any anchor claim passes

Relevant public pages:
- https://github.com/original-bitcoin-laboratory/genesis/tree/main/derivatives/bitcoin
- https://github.com/original-bitcoin-laboratory/genesis/blob/main/derivatives/bitcoin/net.py
- https://github.com/original-bitcoin-laboratory/genesis/blob/main/derivatives/bitcoin/bitcoin-v0.1.0.patch
- https://github.com/trottier/original-bitcoin/blob/master/src/main.h
- https://github.com/trottier/original-bitcoin/blob/master/src/main.cpp
