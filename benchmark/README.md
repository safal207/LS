# Benchmark Package

This directory contains the benchmark artifact for LS, focused on operator workflow efficiency in replayable approval-queue review.

## What is measured

The benchmark does not claim general model superiority or universal speed improvements.

It measures a specific, safety-adjacent property: whether LS reduces operator coordination overhead when reviewing a queue of approval-sensitive tasks, while keeping the review path auditable and replayable.

## Sources

| Source | Contents |
|---|---|
| [`ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json`](../ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json) | Raw timing and command-count measurements for three review scenarios |
| [`artifacts/fellowship-dataset/manifest.json`](../artifacts/fellowship-dataset/manifest.json) | Curated council-ledger sample with contribution and resonance signals |

## Files in this directory

| File | Contents |
|---|---|
| `RESULTS.md` | Generated snapshot - do not edit by hand |
| `INTERPRETATION.md` | How to read the numbers, what they justify, what they do not |
| [`../BENCHMARK_CHANGELOG.md`](../BENCHMARK_CHANGELOG.md) | Time-series record of benchmark evidence updates |

## Regenerating RESULTS.md

```bash
python scripts/generate_benchmark_results.py
```

This reads the two source files above and writes `benchmark/RESULTS.md`. The output is deterministic given the same sources.

## Full methodology note

See [`docs/FELLOWSHIP_BENCHMARK_NOTE.md`](../docs/FELLOWSHIP_BENCHMARK_NOTE.md) for:
- benchmark goal and framing
- baseline definitions
- threats to validity
- recommended next upgrades
