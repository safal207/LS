# Grant Reviewer Path

For grant, fellowship, safety research, or open-source infrastructure review, start here:

- [`docs/GRANT_REVIEWER_PATH.md`](docs/GRANT_REVIEWER_PATH.md)

This reviewer path explains:

- what LS is;
- what is implemented now;
- how to run the Session Continuity Repair Layer demo;
- how continuity events become audit reports;
- how LS relates to CML, PythiaLabs, and LTP;
- what is implemented vs roadmap.

Core chain:

```text
session rupture
-> continuity event
-> causal validity check
-> evidence/action gate
-> trace/replay inspection
-> audit artifact
```

Main repository:

- https://github.com/safal207/LS

Related repositories:

- Causal Memory Layer: https://github.com/safal207/Causal-Memory-Layer
- PythiaLabs: https://github.com/safal207/pythiaLabs
- Liminal Thread Protocol: https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-
