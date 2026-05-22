# Cooperative Precision Metrics

Status: **working local research MVP**.

This document defines the first measurable vocabulary for LS cooperative
precision.

The goal is not to ask which model is globally smarter. The goal is to measure
which cooperative route made one concrete task more precise.

```text
model intelligence stays external
network precision compounds inside LS
```

## Metric Table

| Metric | Meaning | First Use |
|---|---|---|
| `baseline_reward` | Score from a direct or single-pass route. | Compare against cooperative route. |
| `cooperative_reward` | Score from a role-based cooperative route. | Estimate route value. |
| `lift` | `cooperative_reward - baseline_reward`. | Measure improvement. |
| `positive_lift` | Whether `lift > 0`. | Check if cooperation helped. |
| `positive_lift_count` | Number of runs with positive lift. | Batch benchmark summary. |
| `top_role` | Role with the strongest measured contribution. | Contribution attribution. |
| `top_actor` | Actor assigned to the top contributing role. | Actor-level attribution. |
| `noisy_actor` | Actor that adds unsupported claims, false positives, or low-value latency. | Route pruning. |
| `repeatable_route` | Route that should be tried again for similar tasks. | Trail reuse. |
| `needs_more_runs` | Whether the result is too small to treat as validated. | Anti-overclaim guard. |
| `nash_route_stability` | Whether a cooperative route beats single-route and ablation counterfactuals. | Nash-style stability probe. |

## Baseline Reward

`baseline_reward` is the measured signal from a direct route.

For PR review, the baseline route can be:

```text
pr_review>direct_single_reviewer
```

It is not a universal measure of intelligence. It is a task-local comparison
point.

## Cooperative Reward

`cooperative_reward` is the measured signal from a role-based route.

For PR review, an initial cooperative route can be:

```text
pr_review>draft_reviewer>risk_critic>evidence_verifier>final_reviewer
```

The cooperative route should be judged by evidence, not by vibes.

## Lift

`lift` is the simplest improvement metric:

```text
lift = cooperative_reward - baseline_reward
```

Example from the current local PR Role Market benchmark:

```text
baseline_reward:    0.5943
cooperative_reward: 0.7233
lift:               +0.1290
positive_lift:      true
```

Interpretation:

```text
The cooperative route produced a better measured review signal on this small local sample.
```

Non-interpretation:

```text
This does not prove that one model or actor is globally best.
```

## Positive Lift Count

For batches, LS should track how often the cooperative route beats the baseline.

Example:

```text
positive_lift_count: 3/3
```

This is useful but still not enough alone. Small samples must keep
`needs_more_runs: true`.

## Top Role

`top_role` records which function in the route contributed most.

Example:

```text
top_role: risk_critic
```

This means the task benefited from a risk-finding role. It does not mean that
risk critique is always the best role for every task.

## Top Actor

`top_actor` records which actor filled the top role in this run.

Example:

```text
top_actor: gonka
```

This is contribution attribution, not a permanent leaderboard.

## Noisy Actor

A `noisy_actor` is an actor that reduces route precision.

Noise can include:

- unsupported claims;
- false positives;
- repeating already verified claims;
- missing the input boundary;
- increasing latency without improving evidence;
- contradicting grounded evidence.

The metric may be empty when no noisy actor is detected.

## Repeatable Route

A `repeatable_route` is a route worth trying again for similar tasks.

A route can be repeatable even if it is not fully validated yet:

```json
{
  "should_repeat_route": true,
  "needs_more_runs": true,
  "reason": "Positive lift observed, but sample size is still small."
}
```

## Anti-Overclaim Rules

Every metric report should preserve these boundaries:

1. Report sample size.
2. Distinguish role from actor.
3. State whether outputs are real or sample artifacts.
4. Avoid global model-ranking claims.
5. Keep human authority explicit when a route affects action, memory, or reputation.
6. Mark small samples as `needs_more_runs: true`.

## Nash-Style Route Stability

`nash_route_stability` is a practical proxy, not a formal proof of Nash
equilibrium.

It asks a narrower question:

```text
Does the full cooperative route beat the routes where one participant leaves,
the single-route baseline, and a bad role ordering?
```

The first local probe uses:

```text
full route:        pr_review>local>gonka>mimo
single baseline:   pr_review>local
without gonka:     pr_review>local>mimo
without mimo:      pr_review>local>gonka
without local:     pr_review>gonka>mimo
reordered route:   pr_review>mimo>gonka>local
```

The route is marked as `stable_candidate` only when:

- the full route passes Trail MCP success gates;
- the full route beats the single baseline by at least `+0.10`;
- the full route beats the best counterfactual by at least `+0.05`;
- every participant has positive marginal contribution of at least `+0.05`.

Run it locally:

```bash
python scripts/run_nash_route_stability_demo.py
```

Expected interpretation:

```text
The route looks stable when cooperation wins and removing any participant makes
the result less precise.
```

Boundary:

```text
This is Nash-style route stability, not a global economic proof.
```

## Current Metric Snapshot

The first small local benchmark reports:

```text
baseline_reward:    0.5943
cooperative_reward: 0.7233
lift:               +0.1290
positive_lift:      3/3
top_role:           risk_critic
top_actor:          gonka
```

Current interpretation:

```text
LS can measure which cooperation pattern made a concrete PR-review task more precise.
```

Current status:

```text
working local research MVP
```

## Related Artifacts

- [`COGNITIVE_TRAIL_RUN_CONTRACT.md`](COGNITIVE_TRAIL_RUN_CONTRACT.md)
- [`COGNITIVE_TRAIL_NETWORK.md`](COGNITIVE_TRAIL_NETWORK.md)
- [`PR_ROLE_MARKET_BENCHMARK.md`](PR_ROLE_MARKET_BENCHMARK.md)
- [`../schemas/cognitive_trail_run.schema.json`](../schemas/cognitive_trail_run.schema.json)
- [`../examples/trails/pr_review_small_run.json`](../examples/trails/pr_review_small_run.json)
- [`../examples/trails/pr_review_cooperative_result.json`](../examples/trails/pr_review_cooperative_result.json)

## One-Line Claim

```text
Cooperative precision is the measured lift produced by a verified route of roles, actors, and evidence over a baseline attempt.
```
