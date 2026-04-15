# Benchmark Changelog

Tracks benchmark evidence evolution over time for grant/foundation reporting.

## How to use

- Add one entry per benchmark update cycle.
- Keep values factual and reproducible.
- Link the exact data/source commit when possible.

## Entry Template

```md
## YYYY-MM-DD

- Scope: <what was benchmarked>
- Source files:
  - <path>
  - <path>
- Results snapshot:
  - <metric>: <value>
  - <metric>: <value>
- Interpretation:
  - <1-2 lines of what changed>
- Limitations:
  - <known caveats>
- Next actions:
  - <planned benchmark upgrade>
```

## 2026-04-15

- Scope: Initial operator-overhead benchmark evidence package.
- Source files:
  - `ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json`
  - `artifacts/fellowship-dataset/manifest.json`
  - `scripts/generate_benchmark_results.py`
- Results snapshot:
  - Command reduction (manual CLI -> batch LTP): `90.91%`
  - Batch speedup vs manual LTP: `18.11%`
  - Council-ledger sample size: `8`
- Interpretation:
  - Evidence supports reduced operator coordination overhead for replayable review.
  - Evidence does not support universal speed or model-superiority claims.
- Limitations:
  - Single-machine snapshot and small dataset.
  - Several council fields remain `route = "unknown"` in current sample.
- Next actions:
  - Add repeated runs and variance tracking.
  - Expand dataset and introduce human-labeled resonance quality checks.
