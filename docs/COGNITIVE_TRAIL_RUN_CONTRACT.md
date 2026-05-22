# Cognitive Trail Run Contract

Status: **working local research MVP**.

This document defines the first formal contract for a **Cognitive Trail Run** in
LS.

It connects three terms that should stay separate:

```text
LS Cooperative Precision Network = umbrella direction
Cognitive Trail Network          = route-memory mechanism
Cognitive Trail Run              = one recorded measurable run
```

A Cognitive Trail Run is the smallest durable artifact in the Cognitive Trail
Network. It records one task, the cooperative route used to process it, the
evidence observed, the resulting score, the contribution attribution, and the
repeatability decision.

## Core Claim

LS does **not** make individual models internally smarter.

LS makes repeated AI co-work more precise by preserving and evaluating the
routes of cooperation that produced better outcomes.

```text
task
-> route of roles and actors
-> evidence
-> contribution attribution
-> result
-> repeatability decision
```

The next similar task should be able to start from the best known route, not
from zero.

## Non-Goals

A Cognitive Trail Run is not:

- a claim that LS is already a global live network;
- a global ranking of models or people;
- a claim that one actor is permanently best;
- a surveillance log of private behavior;
- an autonomous permission to act without human authority.

It is a local-first, auditable cooperation record.

## Required Fields

| Field | Meaning |
|---|---|
| `schema_version` | Contract version used by the artifact. |
| `task_id` | Stable identifier for this run. |
| `task_type` | Narrow task class, for example `code_review`. |
| `status` | Maturity of the artifact, currently usually `local_research_mvp`. |
| `input_ref` | Reference to the input under review, such as a git diff or commit. |
| `route` | Ordered roles and actors used in the run. |
| `evidence` | Signals that support or weaken the route outcome. |
| `result` | Baseline, cooperative score, lift, and route outcome. |
| `contribution_summary` | Which roles/actors added value or noise. |
| `repeatability` | Whether LS should reuse this route for similar tasks. |

## Role and Actor Boundary

A run must distinguish role from actor.

```text
role  = function in the route
actor = model, tool, service, or human filling that function
```

Example:

```text
role:  risk_critic
actor: gonka
```

This keeps LS from confusing a task-specific contribution with a universal model
ranking.

## Evidence Boundary

Evidence should be concrete where possible.

Good evidence examples:

- git diff reference;
- changed file path;
- test or CI signal;
- accepted/rejected review comment;
- missing test observation;
- unsafe command observation;
- human operator decision.

Weak evidence examples:

- unsupported preference;
- vague confidence statement;
- model reputation without task evidence;
- unverifiable claim about intent.

## Result Semantics

A minimal result compares a direct baseline against a cooperative route:

```text
baseline_reward
cooperative_reward
lift = cooperative_reward - baseline_reward
positive_lift = lift > 0
```

A positive lift means the route improved the measured task signal in this run.
It does not prove that the same route is best globally.

## Repeatability Decision

The repeatability decision is the bridge between one run and the trail network.

A route can be marked:

- `should_repeat_route: true` when evidence suggests it improved precision;
- `should_repeat_route: false` when it added noise, risk, or low-value latency;
- `needs_more_runs: true` when the sample is too small to trust.

## First Applied Wedge: PR Review

The first strong application is:

```text
AI Code Review / PR Review Trail Network
```

Why this wedge works:

- git diffs are explicit inputs;
- tests and CI provide external signals;
- review comments can validate findings;
- risks can be categorized;
- contribution can be measured per role.

## Example Shape

See:

- [`schemas/cognitive_trail_run.schema.json`](../schemas/cognitive_trail_run.schema.json)
- [`examples/trails/pr_review_small_run.json`](../examples/trails/pr_review_small_run.json)
- [`examples/trails/pr_review_cooperative_result.json`](../examples/trails/pr_review_cooperative_result.json)
- [`COOPERATIVE_PRECISION_METRICS.md`](COOPERATIVE_PRECISION_METRICS.md)
- [`COGNITIVE_TRAIL_NETWORK.md`](COGNITIVE_TRAIL_NETWORK.md)
- [`PR_ROLE_MARKET_BENCHMARK.md`](PR_ROLE_MARKET_BENCHMARK.md)

## One-Line Contract

```text
A Cognitive Trail Run records which cooperative route made one concrete task more precise, with evidence strong enough to decide whether that route should be repeated.
```
