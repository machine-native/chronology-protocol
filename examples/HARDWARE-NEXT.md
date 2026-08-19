# Hardware Profile — next stage

Do not change the protocol schema when hardware arrives.

Recommended progression:

1. ordinary GNSS timing receiver exposing raw measurements + 1 PPS
2. multi-GNSS receiver
3. Galileo OSNMA-capable evidence capture
4. disciplined oscillator
5. independent atomic reference
6. secure element / TPM + measured boot
7. geographically and institutionally independent witness deployment

Each driver emits the same SourceObservation/Observation abstraction and commits raw evidence rather
than replacing it with a single vendor-produced wall-clock string.
