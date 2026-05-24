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

## Current Reference Run

With 6 cycles on the current deterministic probe:

```text
no_observer:   0.7436 → 0.7834  (+0.0398, velocity=+0.0080/cycle)
with_observer: 0.7436 → 0.8631  (+0.1195, velocity=+0.0239/cycle)

observer_delta_final:            +0.0797
observer_velocity_multiplier:    2.99x
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
