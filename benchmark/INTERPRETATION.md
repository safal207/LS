# Benchmark Interpretation

This note explains how to read the numbers in `RESULTS.md`, what they justify, and what they do not.

## Context

LS is an operator-facing oversight runtime for human-plus-model systems.

The benchmark is designed to answer one question: does LS make it faster and less error-prone for an operator to review a queue of approval-sensitive tasks, without removing traceability?

This is a safety-adjacent claim, not a general performance claim.

## Scenario definitions

Three review scenarios were measured on a queue of 5 approval-sensitive tasks.

### Manual CLI review (baseline)

The operator uses raw CLI commands - list, inspect, approve, and artifact - one task at a time.

This is the no-tooling baseline. It is the fastest in raw seconds (`15.48s`) but requires `11` commands and leaves no replayable trace structure.

### Manual LTP review

The operator runs one `LTP inspect` call per waiting task.

This preserves replayability but does not yet exploit queue-wide batching. It is slower (`40.26s`) and still requires `5` commands.

### Batch LTP review

The operator runs one queue-wide `ltp-inspect-all` pass for all waiting approvals.

This is the primary LS claim: `32.97s` and only `1` command, while keeping every task trace replayable.

## What the numbers show

The strongest result is not raw speed. It is operator coordination overhead:

- Command count: `11` -> `1` (90.91% reduction)
- Time vs. manual-LTP baseline: 7.29s saved, 18.11% faster
- Every reviewed task remains replayable and auditable

The batch LTP path is slower than manual CLI in raw seconds. This is expected: LTP adds trace-recording overhead. The claim is that the added traceability is worth the extra seconds.

## What the numbers do not show

- The benchmark was run on a single development machine. Results will differ across environments.
- Queue size was 5 tasks. Results may not scale linearly.
- A single snapshot was recorded, not repeated trials. No confidence intervals are available.
- The council-ledger dataset (8 ledgers) is too small for statistical claims about model quality.
- Receiver resonance is currently runtime-derived, not human-annotated. Its precision is unknown.
- Many council cycles still show `model_id = "callable:unknown"` and `route = "unknown"`.

## How to present these results

Accurate framing:

> LS already reduces operator coordination overhead for replayable approval-queue review. One queue-wide inspection pass replaces 11 per-task commands, at a modest latency cost that preserves full traceability.

Do not claim:

- that LS is generally faster than alternatives
- that the council-ledger dataset is statistically significant
- that receiver resonance scores have human-annotation backing

## What would strengthen this benchmark

1. Run repeated trials (10+) to get variance estimates.
2. Increase queue size beyond 5 tasks.
3. Run on multiple machines / environments.
4. Add human annotation for receiver resonance.
5. Resolve `route = "unknown"` in council cycles to enable route-quality analysis.

See `docs/FELLOWSHIP_BENCHMARK_NOTE.md` for the full roadmap.
