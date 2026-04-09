# Benchmark Results

> Generated: 2026-04-09T10:23:54Z
> Source: `scripts/generate_benchmark_results.py`
> Raw data: `ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json`, `artifacts/fellowship-dataset/manifest.json`

---

## 1. Operator workflow benchmark

Benchmark environment: win32, Python 3.11.9, queue size 5.

### Scenarios

| Scenario | Seconds | Commands | Tasks reviewed |
|---|---|---|---|
| `manual_cli_review` | 15.4777 | 11 | 5 |
| `manual_ltp_review` | 40.2597 | 5 | 5 |
| `batch_ltp_review` | 32.9705 | 1 | 5 |

### Summary

| Metric | Value |
|---|---|
| Tasks reviewed | 5 |
| Seconds saved vs manual LTP | 7.2892 |
| Batch speedup vs manual LTP | 18.11% |
| Manual review commands | 11 |
| Batch review commands | 1 |
| Command reduction | 90.91% |

**Strongest result:** command count reduced from `11` to `1` (90.91% reduction) for a queue of 5 approval-sensitive tasks.

**Disclaimer:** This is a local benchmark snapshot on one development machine, not a universal latency claim or legal opinion.

---

## 2. Council-ledger dataset sample

Source: `artifacts/fellowship-dataset/manifest.json`

| Metric | Value |
|---|---|
| Ledger count | 8 |
| Success count | 7 |
| Failure count | 1 |
| Avg receiver resonance | 0.4062 |
| Avg best-contributor score | 0.8345 |

**Excluded from selection:** demo cycles, cid contract fixtures, dry_run:unknown ledgers.

---

## 3. Limitations

- Most cycles currently use callable-backed local LLM outputs but still expose route='unknown'.
- This sample is a curated subset, not a full production dataset.
- Receiver resonance is currently derived from runtime signals rather than human annotation.

---

## 4. What these results support

- LS reduces operator coordination overhead for replayable approval-queue review.
- Structured council-cycle artifacts can be curated into a small evidence dataset.
- The scaffolding for stronger oversight, contribution-attribution, and approval-safe review is operational.

## 5. What these results do not support

- General model superiority.
- Universal latency improvements.
- Statistically strong performance claims across environments.
- Human-annotated resonance or adoption quality.
- Route-quality leadership (many current cycles still expose `route = "unknown"`).

See `docs/FELLOWSHIP_BENCHMARK_NOTE.md` for full methodology and next-upgrade recommendations.
