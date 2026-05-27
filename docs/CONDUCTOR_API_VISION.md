# Conductor API Vision

Status: **product/API vision for turning LS cooperative precision into an API and SDK surface**.

This document reframes LS as a practical conductor layer for better AI results
through model cooperation, evidence, and route memory.

## One-Line Product Claim

```text
Conductor API for better AI results through model cooperation, evidence, and route memory.
```

Shorter slogan:

```text
Stop choosing one model. Choose the best route.
```

## User Problem

Today many users manually compare model outputs:

```text
ask one model
ask another model
ask a local model
compare by hand
lose time
still do not know which answer to trust
```

LS Conductor should turn that into one API call:

```text
task
-> route planning
-> model/role assignment
-> cooperative execution
-> critique and verification
-> final answer
-> evidence trail
-> route memory update
```

The user buys a better verified result, not another chat box.

## Product Wedge

The first product wedge should be:

```text
LS Conductor for PR Review
```

Why this wedge is strong:

```text
real diff input;
clear evidence surface;
existing PR-review trail scripts;
existing role-market demo path;
existing route-stability sample;
clear developer buyer;
clear GitHub integration path;
measurable acceptance / rejection signal.
```

## Existing LS Assets To Reuse

Do not start from scratch. The Conductor API should wrap the current LS evidence
and PR-review stack.

Current reusable surfaces include:

```text
scripts/run_pr_review_trail_demo.py
scripts/run_pr_review_trail_artifact.py
scripts/run_free_pr_review_route.py
scripts/run_role_market_demo.py
scripts/run_pr_role_market_demo.py
scripts/run_pr_role_market_batch.py
scripts/run_nash_route_stability_demo.py
docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md
docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md
docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md
docs/COOPERATIVE_PRECISION_METRICS.md
docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md
docs/ROUTE_STABILITY_EVIDENCE_MAP.md
examples/route-stability/nash_route_stability_sample.json
```

Implementation principle:

```text
thin API facade first;
reuse existing scripts and route artifacts;
only extract reusable services after the API contract is stable.
```

## Core API

### POST /v1/conductor/run

Run one cooperative route.

Request:

```json
{
  "task": "Review this pull request for correctness, security, and product risk.",
  "input": {
    "diff": "...",
    "repo_context": "optional context"
  },
  "goal": "high_precision_pr_review",
  "constraints": {
    "max_cost_usd": 1.5,
    "max_latency_sec": 90,
    "require_evidence": true
  },
  "route_policy": "cooperative_pr_review",
  "models": ["local", "openai", "anthropic"]
}
```

Response:

```json
{
  "final_answer": "...",
  "route_id": "pr_review>draft>critic>verifier>judge",
  "route_score": 0.81,
  "confidence": 0.87,
  "route_won_vs_single": true,
  "disagreements": [
    {
      "topic": "security risk",
      "resolution": "verifier found no direct exploit path in the diff"
    }
  ],
  "evidence": [
    {
      "claim": "The change lacks a regression test for the new branch.",
      "source": "diff",
      "status": "supported"
    }
  ],
  "cost_usd": 0.74,
  "latency_ms": 38120,
  "trace_id": "trail_...",
  "artifact_paths": [
    "reports/trails/..."
  ]
}
```

### POST /v1/conductor/compare

Compare candidate model or route outputs.

Request:

```json
{
  "task": "Write a grant-review summary for this proposal.",
  "candidates": ["gpt", "claude", "local-qwen"],
  "judge_policy": "clarity_evidence_and_nonclaim_safety"
}
```

Response:

```json
{
  "winner": "route: draft>critic>verifier>final",
  "why": [
    "clearer claim boundary",
    "stronger evidence links",
    "less unsupported certainty"
  ],
  "final_output": "..."
}
```

### POST /v1/routes/learn

Record feedback about a route outcome.

Request:

```json
{
  "route_id": "pr_review>local>gonka>mimo",
  "task_type": "pr_review",
  "user_feedback": "accepted",
  "quality_score": 0.9,
  "notes": "Caught a real missing test and avoided a false security claim."
}
```

Response:

```json
{
  "stored": true,
  "route_memory_updated": true
}
```

## SDK Sketch

### TypeScript

```ts
import { LSConductor } from "@ls/conductor";

const ls = new LSConductor({
  apiKey: process.env.LS_API_KEY,
  providers: {
    openai: process.env.OPENAI_API_KEY,
    anthropic: process.env.ANTHROPIC_API_KEY,
    local: "http://localhost:11434"
  }
});

const result = await ls.run({
  task: "Review this PR",
  input: { diff },
  goal: "high_precision_pr_review",
  policy: "cooperative_pr_review",
  requireEvidence: true
});

console.log(result.finalAnswer);
console.log(result.routeId);
console.log(result.evidence);
```

### Python

```python
from ls_conductor import LSConductor

ls = LSConductor(
    api_key="...",
    providers={
        "openai": "...",
        "anthropic": "...",
        "ollama": "http://localhost:11434",
    },
)

result = ls.run(
    task="Review this PR",
    input={"diff": diff},
    goal="high_precision_pr_review",
    policy="cooperative_pr_review",
    require_evidence=True,
)

print(result.final_answer)
print(result.route_score)
print(result.disagreements)
```

## Internal Architecture

```text
HTTP/API layer
-> task classifier
-> route planner
-> model adapter registry
-> role executor
-> evidence verifier
-> route judge
-> trace/artifact writer
-> route memory updater
```

The first version can be a facade over existing LS scripts. Later versions should
extract reusable service functions.

## Model Adapter Interface

A model should be described by capabilities, not only by provider name.

```python
class ModelAdapter:
    name: str
    provider: str
    capabilities: list[str]

    def generate(self, prompt: str, *, role: str, context: dict) -> dict:
        ...

    def estimate_cost(self, prompt: str) -> float:
        ...

    def healthcheck(self) -> bool:
        ...
```

Example model metadata:

```json
{
  "model": "local-qwen",
  "strengths": ["fast", "cheap", "local", "drafting"],
  "best_roles": ["first_pass", "summarizer", "sanity_check"]
}
```

```json
{
  "model": "premium-long-context",
  "strengths": ["long context", "code review", "structured critique"],
  "best_roles": ["architect", "critic", "final_editor"]
}
```

## Route Policies

Initial policies:

| Policy | Use case | Shape |
| --- | --- | --- |
| `single_baseline` | Cheap baseline. | One model, one answer. |
| `cooperative_pr_review` | PR/code review. | draft -> critic -> verifier -> final. |
| `multi_model_verification` | High-stakes analysis. | parallel drafts -> verifier -> judge. |
| `cheap_first_premium_final` | Cost-sensitive flow. | local draft -> cheap critique -> premium final. |
| `evidence_required` | Claims must be anchored. | answer -> evidence verifier -> final. |

## Output Schema Principles

Every Conductor response should expose:

```text
final answer;
route used;
roles used;
model/provider metadata;
evidence items;
disagreements;
route score;
cost;
latency;
trace/artifact id;
claim boundary.
```

This is the product difference: the user sees not only the answer, but why this
route was chosen and what evidence survived review.

## Nash-Style Route Stability As Differentiator

LS should use the existing Nash-style route stability proxy carefully.

Safe claim:

```text
For a bounded task and deterministic probe, LS can test whether a cooperative
route beats a single baseline, participant ablations, and bad-ordering
counterfactuals.
```

Do not claim:

```text
formal Nash equilibrium;
global model ranking;
global route optimality;
statistical sufficiency;
that one route generalizes to all tasks.
```

Product translation:

```text
LS can show when a cooperative route appears more reliable than a single-model
baseline for a bounded task type.
```

## MVP Plan

### MVP 0: Documentation Contract

```text
docs/CONDUCTOR_API_VISION.md
issue: Build minimal Conductor API skeleton
example request/response JSON
```

### MVP 1: Local CLI Facade

```bash
ls-conductor review-pr --diff latest.diff --policy cooperative_pr_review --json
```

Implementation can wrap:

```text
scripts/run_pr_review_trail_artifact.py
scripts/run_free_pr_review_route.py
scripts/run_pr_role_market_demo.py
```

### MVP 2: Local HTTP API

```text
POST /v1/conductor/run
GET /v1/traces/{trace_id}
POST /v1/routes/learn
```

### MVP 3: SDK

```text
Python SDK
TypeScript SDK
examples/pr_review_conductor.py
examples/pr_review_conductor.ts
```

### MVP 4: GitHub App / Bot

```text
@ls review
@ls review --high-precision
@ls explain-route
```

## Pricing / Product Wedge

Potential packaging:

| Tier | Value |
| --- | --- |
| Free | Local-only route runner, limited policies, examples. |
| Pro | Multi-provider Conductor API, saved traces, route memory. |
| Team | GitHub integration, shared route library, CI evidence reports. |
| Enterprise | Self-hosting, private adapters, audit exports, policy controls. |

## What Would Make Users Say Wow

A strong PR-review result should show:

```text
Route used:
draft(local) -> critic(premium) -> verifier(structured) -> final(premium)

Why this route won:
+ found 3 review issues
+ removed 2 unsupported claims
+ verified 5 evidence items
+ cost: $0.41
+ confidence: 0.86
+ accepted on 14/17 similar PR-review trails
```

## Risks

| Risk | Mitigation |
| --- | --- |
| Too broad | Start with PR Review Conductor only. |
| Too philosophical | Show API, SDK, JSON, screenshots, and examples. |
| Too expensive | Use cheap-first / local-first routes. |
| Too slow | Offer `fast`, `balanced`, and `high_precision` modes. |
| Overclaiming | Preserve route-stability proxy boundary. |
| Hard to trust | Always return evidence, disagreement, trace, and route metadata. |

## Non-Claims

Conductor API does not claim:

```text
one model is globally best;
one route is globally optimal;
formal Nash equilibrium;
statistical sufficiency without benchmarks;
production compliance without deployment-specific controls;
that all tasks benefit from multi-model cooperation.
```

## Bottom Line

The strongest product version of LS is not a generic agent marketplace.

It is:

```text
cooperative AI route orchestration + evidence + route memory
```

The first commercial wedge should be:

```text
PR Review Conductor
```

The first developer promise should be:

```text
Send one task. Get the best cooperative route result, with evidence.
```
