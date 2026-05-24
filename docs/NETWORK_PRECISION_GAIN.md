# Network Precision Gain

Status: **deterministic proxy metric**.

Network Precision Gain answers one question:

```text
How much precision did the cooperative network add over a single answer?
```

It separates two claims:

1. **Measured route reward gain** — already produced by the Nash-style route
   stability probe.
2. **Full stack precision gain** — a proxy score that adds support from trace,
   evidence gates, living memory, reflection, depth fit, and human boundary.

## Run

```bash
python scripts/run_network_precision_gain_demo.py
python scripts/run_network_precision_gain_demo.py --json
```

Regression test:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_network_precision_gain_demo.py
```

## Current Local Result

The deterministic demo currently reports:

```text
single baseline score:      0.1603
cooperative route score:    0.7186
full stack score:           0.8628

measured route reward gain: +0.6656
network precision gain:     +0.7025
stack added gain:           +0.1442
ratio vs baseline:          5.3824x
```

Interpretation:

```text
The cooperative route already beats the single route on measured reward.
The surrounding stack adds precision by making the route traceable, gated,
adaptive, reflective, depth-aware, and human-bounded.
```

## Components

| Component | Meaning |
| --- | --- |
| `route_reward` | The measured LS route reward from role cooperation. |
| `evidence_gate` | Support from Pythia-style evidence/action gating. |
| `trace_integrity` | Support from TTM-style immutable transition trace. |
| `adaptive_memory` | Support from LiminalDB-style repeatable living route memory. |
| `reflective_clarity` | Support from RINSE-style interpretation over experience. |
| `human_boundary` | Human goal, consent, review, and acceptance boundary. |
| `depth_fit` | Whether the route ran at the right Depth Economy level. |

Default weights:

```text
route_reward       0.40
evidence_gate      0.16
trace_integrity    0.12
adaptive_memory    0.12
reflective_clarity 0.10
human_boundary     0.06
depth_fit          0.04
```

## Why This Matters

Without this metric, the project can only say:

```text
the cooperative route looked better
```

With this metric, LS can say:

```text
the route reward improved by X
the full network precision proxy improved by Y
the stack layer added Z over raw cooperation
```

That gives contributors a concrete target:

- improve evidence gating;
- improve immutable trace linking;
- improve route memory repeatability;
- improve reflection clarity;
- improve human acceptance boundaries;
- improve depth fit.

## Boundary

This metric is not a final benchmark. It is a first engineering proxy for
tracking whether the stack is making repeated cooperation more precise.

Do not present it as:

- proof of AI consciousness;
- proof of global model superiority;
- proof of production safety;
- proof of formal Nash equilibrium.

The narrow claim is:

```text
LS can measure how much more precise a cooperative route plus evidence stack is
than a single answer on the current deterministic local probe.
```
