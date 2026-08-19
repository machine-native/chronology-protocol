# Protocol Invariants

1. **No calendar is consensus.** Calendars are projections over chronology.
2. **No clock is authoritative.** Every accepted physical-time claim is evidence-backed.
3. **No exactness without uncertainty.** Physical observations are intervals.
4. **No silent correction.** Corrections and conflicts append; prior evidence is never replaced.
5. **No single physical source.** GNSS, local oscillators and future sources remain separable.
6. **No single witness/operator.** Quorum policy is explicit and independently reproducible.
7. **No single cryptographic primitive.** Production v1 uses independent hash and signature families.
8. **No single blockchain.** Bitcoin is an anchor adapter, not the definition of chronology.
9. **No destructive upgrade.** Renewals encapsulate prior evidence; they do not migrate/delete it.
10. **Offline deterministic verification.** Given the evidence package and suite implementations, a
    third party can reproduce the protocol verdict without trusting the producer.
11. **Bitcoin `nTime` is metadata, not physical-time evidence.**
12. **Witness identity is not a key.** Keys rotate; evidentiary lineage persists.
13. **Failure may be the correct result.** `TIME_CONFLICT` and `ORDER_INDETERMINATE` are valid.
14. **Claims cannot exceed evidence.** A simulator cannot establish a GNSS or hardware claim.
