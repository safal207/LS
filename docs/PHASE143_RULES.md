# Phase 14.3 Fuzzy Rules

## Inputs and memberships

### `queue_load`
- low: descending ramp over `0.0 .. 0.3`
- medium: implicit overlap (used by transition behavior)
- high: ascending ramp over `0.6 .. 1.0`

### `batch_efficiency`
- underutilized: descending ramp over `0.0 .. 0.4`
- optimal: triangular over `0.3 .. 0.55 .. 0.8`
- saturated: implicitly represented by high efficiency with weaker increase response

### `burst_pressure`
- calm: descending ramp over `0.0 .. 0.2`
- moderate: overlap region
- storm: ascending ramp over `0.6 .. 1.0`

### `drop_rate`
- low/none: descending ramp over `0.0 .. 0.05`
- critical: ascending ramp over `0.05 .. 1.0`

## Rule set

### Throughput (`max_signals_per_tick`)
- Increase moderately when `queue_load` is high and `batch_efficiency` is optimal.
- Decrease slightly when `queue_load` is low and `batch_efficiency` is underutilized.
- Decrease aggressively when `drop_rate` is critical.

### Queue capacity (`max_queue_size`)
- Increase moderately when `burst_pressure` is storm and `drop_rate` is low.
- Decrease slightly when queue stays low and burst pressure is calm.

### Governance priority (`priority_boost`)
- Boost when `burst_pressure` is storm and `queue_load` is high.
- Reduce toward baseline when queue load is low.

## Defuzzified outputs

The current implementation uses weighted linear factors and clamps:

- throughput factor: `[0.4, 1.6]`
- queue factor: `[0.7, 1.4]`
- priority boost: `[0.5, 3.0]`

All outputs are clamped to regulator safety bounds before applying to the bus.
