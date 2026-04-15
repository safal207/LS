# Fellowship Benchmark Note

This note summarizes the current benchmark-style evidence in the repository for fellowship review.

It is intentionally narrow. The goal is to show what has been measured already, what the current baseline is, and what the results do and do not justify.

## Benchmark goal

The current benchmark does not attempt to prove that LS is a generally faster agent system.

Instead, it measures a more specific claim:

- whether LS reduces operator effort when reviewing a queue of approval-sensitive tasks
- whether queue-wide replay and inspection is more efficient than per-task review
- whether the review path remains auditable and replayable

This matches the repository's safety framing better than a generic latency benchmark.

## Current evidence sources

- [`ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json`](../ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json)
- [`artifacts/fellowship-dataset/manifest.json`](../artifacts/fellowship-dataset/manifest.json)
- [`artifacts/fellowship-dataset/README.md`](../artifacts/fellowship-dataset/README.md)

The operator benchmark provides measured timing and command-count deltas for queue review workflows.

The fellowship dataset provides a curated sample of real council-ledger artifacts that show the current quality and limitations of council-cycle evidence.

## Baseline and comparison scenarios

The operator benchmark uses a queue of `5` approval-sensitive tasks and compares three scenarios.

### 1. Manual CLI review

Definition:

- operator uses list, inspect, approval, and artifact commands task by task

Measured result:

- `15.4777` seconds
- `11` commands
- `5` tasks reviewed

Interpretation:

- this is the baseline for a human operator using raw CLI flows

### 2. Manual LTP review

Definition:

- operator runs one `LTP inspect` call per waiting task

Measured result:

- `40.2597` seconds
- `5` commands
- `5` tasks reviewed

Interpretation:

- this is the baseline for per-task replay and inspection
- it preserves replayability but does not yet exploit queue-wide batching

### 3. Batch LTP review

Definition:

- operator runs one queue-wide `ltp-inspect-all` pass for waiting approvals

Measured result:

- `32.9705` seconds
- `1` command
- `5` tasks reviewed

Interpretation:

- this is the best current demonstration of LS reducing operator effort without removing traceability

## Measured deltas

From the recorded benchmark snapshot:

- `7.2892` seconds saved versus manual per-task LTP review
- `18.11%` speedup versus manual per-task LTP review
- command count reduced from `11` to `1`
- `90.91%` command reduction for queue review

The strongest current result is not absolute speed. It is the reduction in operator coordination overhead.

## What the fellowship dataset adds

The benchmark above is about operator workflow.

The curated fellowship dataset adds a second kind of evidence: council-cycle outputs with measurable contribution signals.

Current curated sample:

- `8` ledger artifacts
- `7` successes
- `1` failure
- average receiver resonance: `0.4062`
- average best-contributor score: `0.8345`

This does not yet form a strong statistical benchmark, but it shows that the repository already produces structured artifacts that can support one.

## Metrics used

The current note relies on five practical metrics:

- wall-clock seconds for review workflow
- command count
- tasks reviewed
- receiver resonance in council-ledger outputs
- best-contributor score in council-ledger outputs

These are intentionally operator-facing metrics. They are easier to defend than vague claims about general intelligence or universal model quality.

## What this benchmark supports

The current evidence supports a modest claim:

- LS already reduces operator coordination overhead for replayable approval review
- LS already emits structured council-cycle artifacts that can be curated into a small evidence dataset
- LS already provides the scaffolding for a stronger benchmark on oversight, contribution attribution, and approval-safe decision review

## What this benchmark does not support yet

The current evidence does not justify the following claims:

- general model superiority
- universal latency improvements
- statistically strong performance claims across environments
- human-annotated resonance or adoption quality
- route-quality leadership, because many current cycles still expose `route = "unknown"`

## Threats to validity

The current benchmark has several important limitations:

1. It is a local benchmark snapshot on one development machine.
2. The queue size is small: `5` tasks.
3. The curated council dataset is also small: `8` selected ledgers.
4. Many real local cycles still show `model_id = "callable:unknown"`.
5. Many real local cycles still show `route = "unknown"`.
6. Receiver resonance is currently runtime-derived, not independently human-annotated.

These are real weaknesses and should be stated plainly in the application package.

## Next benchmark upgrades

The most valuable next upgrades are:

1. grow the council dataset beyond `8` curated ledgers
2. add replay traces to `artifacts/fellowship-dataset/traces/`
3. improve local council metadata so routes are not left as `unknown`
4. run repeated queue-review trials instead of a single snapshot
5. add human review labels for resonance and adoption quality

## Bottom line

This repository already contains a credible early benchmark artifact, but it should be presented as:

- a narrow operator-oversight benchmark
- a compact evidence package
- a stepping stone toward a stronger safety-evaluation benchmark

That framing is accurate, defensible, and aligned with the current state of the codebase.
