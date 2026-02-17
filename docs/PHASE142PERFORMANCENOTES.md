# Phase 14.2 Performance Notes

## Scope

Phase 14.2 focuses on performance polishing for the deterministic signal pipeline in high-load clusters (1000+ agents).

## Implemented optimizations

- Batch extraction in `DeterministicSignalBus.process_tick()` now uses `itertools.islice()` and a controlled dequeue drain.
- Added a fast-path for empty pending queues: immediate return without lock acquisition.
- Locking is constrained to two critical sections:
  1. take batch + mark processing
  2. update metrics + clear processing flag
- Added new metrics in `SignalBusMetrics`:
  - `avgbatchsize`: running average of effective batch size per processed signal volume.
  - `queuepeakper_tick`: observed peak queue depth at tick start.

## Monitoring implications

- `avgbatchsize` helps detect underutilized ticks and tune `max_signals_per_tick`.
- `queuepeakper_tick` highlights burst pressure and helps pre-tune queue bounds for governance in Phase 15.

## Validation

- Unit tests cover new metrics and processing behavior.
- Added a performance regression guard for a 50k signal batch processing budget.
