# Network Trajectory Layer

Status: **growth probe for repeated cooperative route precision over time**.

The Network Trajectory Layer answers a question that static probes cannot:

```text
Does the network become more precise from run to run?
```

It builds on the [Network Precision Gain](NETWORK_PRECISION_CONTRIBUTOR_CALL.md) metric
and adds a temporal growth dimension: the same cooperative route is repeated across
multiple cycles, with and without the external observer, to measure **velocity**,
**delta**, and **convergence** of precision over time.

## Core Idea

Most evaluation asks:

```text
Which route is better in one run?
```

The trajectory layer asks:

```text
Route A after 20 repeats becomes more stable.
The observer starts catching errors earlier.
The network learns to pick better routes.
Bad routes decay, good routes consolidate.
```

This is **route learning without model training** — the models stay the same,
but the cooperative network around them becomes more precise because it
remembers and improves verified trajectories.

## Metrics

### Precision Velocity

```text
precision_velocity = (score_end - score_start) / (cycles - 1)
```

How fast does precision improve per cycle?

### Observer Delta

```text
observer_delta = score_with_observer - score_without_observer
```

How much value does the external observer add over the same trajectory?

### Velocity Multiplier

```text
velocity_multiplier = observer_velocity / no_observer_velocity
```

How many times faster does the network grow with the observer?

### Drift Reduction, Lag Reduction, Resonance Gain

Changes in temporal coherence between the first and last cycle:

```text
drift_reduction = drift_start - drift_end
lag_reduction   = lag_start - lag_end
resonance_gain  = resonance_end - resonance_start
```

### Route Selection Confidence and Regret

- **confidence**: how reliably the network selects the best known route
- **regret**: how much precision is lost by exploring suboptimal routes

### Reason Memory (Co-Learning Layer)

Every cycle, the observer extracts **causal reasons** for what changed and why:

```text
cycle 2: drift narrowed by 0.072 — levels individual<->environment are synchronizing
         resonance grew by 0.099 — cross-level alignment is strengthening
         observer added +0.016 precision — error pattern detected and flagged
```

Across all cycles, a **co-learning summary** is built:

- **causal_patterns**: which signals changed most frequently
- **error_to_resource_conversions**: errors that became learning signals
- **learned_constraints**: discovered relationships (e.g., "drift and resonance are anti-correlated")
- **network_maturity**: `early` / `developing` / `converging`

This is **memory of causes, not just facts** — the network remembers *why* a route worked, not just *that* it worked.

## Current Reference Run

With 6 cycles on the current deterministic probe:

```text
no_observer:   0.7436 → 0.7834  (+0.0398, velocity=+0.0080/cycle)
with_observer: 0.7436 → 0.8631  (+0.1195, velocity=+0.0239/cycle)
conductor v0.2:0.7436 → 0.8698  (+0.1262, velocity=+0.0252/cycle)

observer_delta_final:            +0.0797
observer_velocity_multiplier:    2.99x
conductor_observer_delta:        +0.0067
conductor_velocity_multiplier:   3.15x
conductor_harmony_index:         0.9925
trajectory_gain_over_baseline:   +0.7208

drift_reduction:                 +0.3600
lag_reduction:                   +0.2700
resonance_gain:                  +0.4950
temporal_alignment_gain:         +0.5400
route_selection_confidence_gain: +0.2610
route_regret_reduction:          +0.1260
```

The observer accelerates convergence by approximately **3x** and achieves
the same final precision in roughly **one-third the cycles**.

The conductor v0.2 adds a stricter reason-aware correction policy:

```text
component_update = reason_kind_delta
                 × reason_delta_scale
                 × reason_freshness_decay
```

This prevents stale reasons from matching fresh reasons on longer runs.

### Co-Learning (Reason Memory)

Per cycle, the observer extracts causal reasons. Sample output:

```text
cycle 6 temporal alignment jumped by 0.1096 — all three levels entered phase lock
```

Cross-cycle pattern extraction:

```text
Network maturity: converging
Total causal events: 36
Unique causal patterns: 8
Top patterns:
  - drift_narrowing (5x)
  - resonance_building (5x)
  - lag_decrease (5x)

Error-to-resource conversions:
  cycle 6: temporal alignment jumped — all three levels entered phase lock

Learned constraints:
  - When drift narrows, resonance tends to build — anti-correlated across levels
  - Observer consistently adds +0.01-0.08 precision per cycle
  - Regret decreases monotonically — network learns to avoid suboptimal routes
```

This is what the network "knows" — not just scores, but causal structure.

## Run It

```bash
# Default: 6 cycles
python scripts/run_network_trajectory_demo.py

# 10 cycles
python scripts/run_network_trajectory_demo.py --cycles 10

# Full JSON output
python scripts/run_network_trajectory_demo.py --json
```

## MCP Tool

The probe is available as an MCP tool:

| Tool | Arguments | Returns |
| --- | --- | --- |
| `ls_run_network_trajectory_probe` | `{"cycles": 6}` | Trajectory summary + per-cycle states |

Connect via stdio:

```bash
python -m ls.agent_shell.mcp_server
```

## Schema

The full JSON payload validates against:

```
schemas/network_trajectory.schema.json
```

## Boundary

This is not model training, not a formal learning curve, and not a production
safety claim. The narrow claim is:

```text
LS can measure whether repeated cooperative runs plus an external observer
improve route precision velocity on a deterministic, visible, repeatable probe.
```
