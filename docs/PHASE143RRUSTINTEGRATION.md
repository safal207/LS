# Phase 14.3-R Rust Integration

Phase 14.3-R adds an optional Rust acceleration layer for fuzzy adaptation and signal batch shaping.

## What is moved to Rust

New crate: `ncafuzzycore`.

Exported via PyO3:

- `compute_adjustments(metrics: PySignalMetrics, config: PyBusConfig) -> PyAdjustments`
- `process_batch(signals: Vec<PySignal>, config: PyBusConfig) -> PyBatchResult`

`compute_adjustments` mirrors Phase 14.3 fuzzy inputs and emits bounded adaptive outputs:

- `max_signals_per_tick`: `[1000, 100000]`
- `max_queue_size`: `[10000, 1000000]`
- `priority_boost`: `[0.0, 0.3]`

## Python integration

`python/modules/nca/signals.py` loads Rust module opportunistically:

- If `ncafuzzycore` is importable, `DeterministicSignalBus._apply_regulator()` uses Rust.
- If import fails or Rust function raises, bus falls back to Python `FuzzyLoadRegulator`.

This keeps deterministic behavior intact while enabling optional acceleration.

## Build options

### maturin

```bash
cd ncafuzzycore
maturin develop --release
```

### fallback mode

If module is not installed, no extra action is needed. Python path remains fully functional.

## Testing

- Rust unit tests and property tests are located in `ncafuzzycore/src/lib.rs`.
- Python tests validate both Rust-available path (mocked) and fallback behavior.
