# Cognitive Trail PR-Review Benchmark Note

Status: **working local research MVP**.

This note is a short, reviewer-facing benchmark card for the first Cognitive
Trail PR-review result in LS.

It complements:

- [`PR_ROLE_MARKET_BENCHMARK.md`](PR_ROLE_MARKET_BENCHMARK.md)
- [`COOPERATIVE_PRECISION_METRICS.md`](COOPERATIVE_PRECISION_METRICS.md)
- [`COGNITIVE_TRAIL_RUN_CONTRACT.md`](COGNITIVE_TRAIL_RUN_CONTRACT.md)
- [`COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md`](COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md)

## Research Question

The benchmark asks one narrow question:

```text
Can LS measure whether a cooperative PR-review route produces a better local review signal than a direct single-reviewer baseline?
```

It does **not** ask which model is globally best.

## Artifact Under Test

The measurable artifact is a **Cognitive Trail Run**.

For PR review, a trail run records:

```text
git diff or commit window
-> route of reviewer roles and actors
-> evidence signals
-> baseline reward
-> cooperative reward
-> lift
-> top role and actor
-> repeatability decision
```

The canonical checked-in sample is:

```text
examples/trails/generated_pr_review_sample.json
```

## Routes Compared

Baseline route:

```text
pr_review>direct_single_reviewer
```

Cooperative route:

```text
pr_review>draft_reviewer>risk_critic>evidence_verifier>final_reviewer
```

The cooperative route separates the review into functions:

| Role | Purpose |
| --- | --- |
| `draft_reviewer` | Creates the first review surface. |
| `risk_critic` | Finds missing tests, large-diff pressure, unsafe changes, weak evidence, or hold signals. |
| `evidence_verifier` | Checks whether findings are grounded in visible diff evidence. |
| `final_reviewer` | Produces the final human-facing review decision. |
| `final_authority` | Keeps human authority explicit before route reuse. |

## Metric Definition

The primary metric is cooperative lift:

```text
lift = cooperative_reward - baseline_reward
positive_lift = lift > 0
```

Secondary fields:

```text
top_role
top_actor
should_repeat_route
needs_more_runs
```

These fields make the result reusable as a Cognitive Trail artifact rather than
only a one-off score.

## Current Snapshot

Current checked-in benchmark snapshot:

```text
analyzed:             3/3
errors:               0
baseline_reward:      0.5943
cooperative_reward:   0.7233
lift:                 +0.1290
positive_lift:        3/3
top_role:             risk_critic
top_actor:            gonka
repeatability:        should_repeat_route=true, needs_more_runs=true
```

Interpretation:

```text
On the current small local PR-review sample, the cooperative route produced a better measured review signal than the direct baseline.
```

The most useful role was `risk_critic`, which suggests that these diffs benefited
from an explicit risk-finding phase before final review.

## Reproduction Path

Install the validator dependency:

```bash
python -m pip install jsonschema
```

Validate checked-in Cognitive Trail examples:

```bash
python scripts/validate_cognitive_trail_runs.py
```

Run the PR Role Market batch benchmark:

```bash
python scripts/run_pr_role_market_batch.py --last 3
```

Generate and validate a runtime Cognitive Trail Run:

```bash
python scripts/generate_pr_review_trail_run.py --last 10 --validate
```

Generated runtime reports are written to:

```text
reports/trails/<timestamp>_pr_review_trail_run.json
```

Those runtime JSON files are ignored by git. The stable reviewer sample is kept
under:

```text
examples/trails/generated_pr_review_sample.json
```

## Validation Path

The Cognitive Trail validator checks:

- JSON validity;
- Draft 2020-12 schema validity;
- `schema_version == cognitive_trail_run.v0.1`;
- `lift == cooperative_reward - baseline_reward`;
- `positive_lift` matches the sign of `lift`;
- route steps are contiguous from `1`;
- `top_role` is present in the recorded route;
- `top_actor` is present in the recorded route;
- contribution summary agrees with result fields.

The workflow gate is:

```text
.github/workflows/cognitive_trail_contract.yml
```

## Why This Is a Cognitive Trail Result

A normal benchmark usually stops at a score.

This benchmark emits a route artifact:

```text
score
+ route
+ evidence
+ contribution attribution
+ repeatability decision
```

That is the important distinction. LS is not only asking whether a route scored
better once. It is asking whether the route should be tried again for similar
future tasks.

## Non-Claims

This note does not claim:

- global model ranking;
- that `gonka` is globally better than other actors;
- that `risk_critic` is always the best role;
- production-grade evaluation;
- that LS already runs a global live Cognitive Trail Network;
- that the current sample is statistically sufficient.

The current claim is narrower:

```text
LS can record and validate a local PR-review trail showing positive measured lift for a cooperative route over a direct baseline.
```

## Current Limitations

Current limitations:

- sample size is small;
- scoring is deterministic and heuristic;
- attached role outputs may be sample artifacts unless replaced by real actor outputs;
- CI/test outcomes and post-merge outcomes are not yet part of the metric;
- no external benchmark corpus is included yet;
- the result should remain marked `needs_more_runs: true`.

## What Would Strengthen the Result

The strongest next evidence artifacts would be:

1. A curated suite of PR-review diffs: docs-only, missing-tests, large-diff, unsafe-command, and false-positive cases.
2. Real attached role outputs from Codex, local Qwen, human review, or configured backends.
3. CI/test outcome signals added to the reward calculation.
4. Post-review human acceptance or rejection labels.
5. More generated trail runs promoted into stable checked-in examples.

## One-Line Benchmark Claim

```text
On a small local PR-review sample, LS measured positive lift from a cooperative review route and converted that result into a validated Cognitive Trail Run artifact.
```
