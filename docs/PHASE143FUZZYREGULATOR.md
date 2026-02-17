# Phase 14.3 Fuzzy Adaptive Deterministic Pipeline

## Goal

Phase 14.3 introduces adaptive control over deterministic signal processing using fuzzy logic so that the system can automatically tune throughput, queue capacity, and governance priority under changing load.

## New component: `FuzzyLoadRegulator`

`python/modules/nca/signals.py` now includes `FuzzyLoadRegulator`, which consumes `SignalBusMetrics` and computes three adaptive outputs:

- `max_signals_per_tick`
- `max_queue_size`
- `priority_boost`

The regulator evaluates normalized inputs:

- `queue_load = queue_size / max_queue_size`
- `batch_efficiency = avgbatchsize / max_signals_per_tick`
- `burst_pressure = queuepeakper_tick / max_queue_size`
- `drop_rate = total_dropped / total_emitted`

## Integration in `DeterministicSignalBus`

`DeterministicSignalBus` now owns:

- `self.regulator: FuzzyLoadRegulator`
- `self.priority_boost: float`

At the end of each `process_tick()` cycle (including idle ticks), `_apply_regulator()` is called and updates runtime limits. This keeps the deterministic pipeline adaptive without introducing nondeterministic ordering.

## Safety bounds

Adaptive outputs are bounded to avoid unstable oscillations:

- throughput: bounded by regulator min/max `signals_per_tick`
- queue size: bounded by regulator min/max queue size
- priority boost: clamped to `[0.5, 3.0]`

## Validation highlights

- High load + efficient batches increase throughput.
- Critical drop rate triggers aggressive throughput reduction.
- Burst periods lift throughput; calm periods gradually reduce it.


## Phase 14.3-R optional acceleration

A companion optional Rust layer (`ncafuzzycore`) can serve `compute_adjustments` for the same metrics contract. Python integration is best-effort with automatic fallback to this pure-Python regulator if Rust is not available.


## Stability and observability updates

- Regulator outputs are damped with EMA (`alpha=0.3`) before applying to bus runtime limits, reducing oscillations during rapidly changing load.
- `SignalBusMetrics.regulator_adjustment_count` tracks how often the regulator applies updates.
- Significant parameter shifts (>10% in throughput or queue limit) are logged for production monitoring.
- `avgbatchsize` now uses a sliding window over the last 1000 processed ticks to limit long-run precision drift.
