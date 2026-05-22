# LS Cognitive Trail Network

LS Cognitive Trail Network is the cooperative route-memory layer for AI co-work.

The core idea:

```text
Models do not only answer.
They leave trails.
LS remembers which trails worked.
```

Contributor roadmap:

- [Cooperative Precision Roadmap](COOPERATIVE_PRECISION_ROADMAP.md)
- [Cognitive Trail Run Contract](COGNITIVE_TRAIL_RUN_CONTRACT.md)
- [Cooperative Precision Metrics](COOPERATIVE_PRECISION_METRICS.md)
- [PR Role Market Benchmark](PR_ROLE_MARKET_BENCHMARK.md)

Instead of treating every model call as a fresh isolated attempt, LS records the
route that produced a result: which roles participated, what quality signals
were observed, where the route needed repair, and whether the outcome was safe
to reuse. The next agent group can start from the best known route instead of
wandering from zero.

The goal is precision, not vague intelligence:

```text
model intelligence stays external
network precision compounds inside LS
```

## Mountain Trail Metaphor

Each agent is like a group crossing a mountain path.

- A weak path is remembered as risky or slow.
- A reliable path is marked on the map.
- A better path can replace the previous best route.
- A route that needs human review is marked before others follow it.

This is close to ant-colony search, but LS stores auditable signals instead of
opaque pheromones:

- route key
- participants and roles
- quality score
- goal alignment
- latency
- hallucination risk
- contribution ledger
- continuity and evidence events
- replayable audit artifact

## Trail Run Contract

The smallest durable artifact in the network is now a **Cognitive Trail Run**:

```text
task
-> route of roles and actors
-> evidence
-> contribution attribution
-> result
-> repeatability decision
```

A trail run is not a claim that LS has become a global live model network. It is
a local-first, auditable cooperation record that can be validated, compared, and
replayed.

Canonical artifacts:

- [`docs/COGNITIVE_TRAIL_RUN_CONTRACT.md`](COGNITIVE_TRAIL_RUN_CONTRACT.md)
- [`docs/COOPERATIVE_PRECISION_METRICS.md`](COOPERATIVE_PRECISION_METRICS.md)
- [`../schemas/cognitive_trail_run.schema.json`](../schemas/cognitive_trail_run.schema.json)
- [`../examples/trails/pr_review_small_run.json`](../examples/trails/pr_review_small_run.json)
- [`../examples/trails/pr_review_cooperative_result.json`](../examples/trails/pr_review_cooperative_result.json)

## What Exists Today

The repository already has the main building blocks:

- `python/modules/graph/cooperative_engine.py` coordinates role-based model routes.
- `python/modules/graph/path_selector.py` chooses routes using prior route stats.
- `python/modules/graph/trail_updater.py` computes route reward and updates `pheromone_weight`.
- `python/modules/graph/route_stats.py` stores route quality, runs, success count, and latency.
- `python/ls/cognition/council_contribution_ledger.py` records who contributed what.
- `docs/COOPERATIVE_MERITOCRACY_NETWORK.md` describes the broader cooperative model network.
- `docs/MERIT_LEDGER_CONSENSUS.md` describes merit and contribution consensus.
- `docs/COGNITIVE_TRAIL_RUN_CONTRACT.md` defines the first formal trail-run contract.
- `schemas/cognitive_trail_run.schema.json` defines the first machine-readable trail-run schema.
- `examples/trails/` contains initial PR-review trail-run examples.
- `python/ls/agent_shell/trail_network.py` exposes the first local MCP bridge for route memory.

## MCP Bridge v0.2

The first MCP-facing bridge is documented in
[`LS_TRAIL_MCP_SERVER.md`](LS_TRAIL_MCP_SERVER.md).

It lets connected agents interact with the network through five local tools:

```text
ls_trail_recommend_route
ls_trail_submit_contribution
ls_trail_validate_evidence
ls_trail_record_outcome
ls_trail_query_best_trails
```

This is the first practical way for external models to connect to LS route
memory:

```text
ask for the best known route
-> submit role output
-> validate evidence
-> record human / CI / task outcome
-> update local route memory
```

The bridge is still local-first and does not update model weights. It makes the
network more precise by updating route memory only after evidence or outcome
signals exist.

The current metric version is `trail_mcp_metrics.v0.2`. A route is not counted
as successful just because it received a positive reward. It must pass evidence
coverage, low false-positive rate, and human or CI confirmation gates. This
keeps the network focused on precision rather than optimistic scoring.

To test the practical signal:

```bash
python scripts/run_trail_mcp_metrics_demo.py
```

To test whether the cooperative route is Nash-style stable against simple
counterfactuals:

```bash
python scripts/run_nash_route_stability_demo.py
```

## Product Shape

The first concrete product should be narrow:

```text
AI Code Review / PR Review Trail Network
```

Why this use case first:

- GitHub tasks have explicit diffs, comments, tests, and CI evidence.
- Review quality can be measured by found risks, false positives, and accepted fixes.
- Routes are easy to compare: single model vs draft -> critic -> verifier.
- Community contributors understand the workflow quickly.

Example route:

```text
PR diff
-> draft reviewer
-> risk critic
-> evidence verifier
-> final review
-> route reward
-> trail map update
```

## Minimal API Direction

The network can begin as a local-first API before becoming a broader mesh:

```text
POST /v1/trails/run
POST /v1/trails/score
GET  /v1/trails/best?task_type=code_review
GET  /v1/routes/{route_key}/reputation
```

The output should always include:

```json
{
  "task_type": "code_review",
  "route_key": "review>draft>critic>verifier",
  "participants": ["local", "gonka", "mimo"],
  "quality_score": 0.91,
  "goal_alignment_score": 0.89,
  "hallucination_risk": 0.08,
  "route_reward": 0.68,
  "pheromone_weight": 1.42,
  "decision": "prefer_for_next_similar_task"
}
```

## Positioning

Market category:

```text
multi-agent orchestration + route memory + contribution ledger + audit
```

Short positioning:

```text
LS gives models a shared map of verified routes.
```

Longer positioning:

```text
Multi-agent systems usually coordinate agents inside one workflow.
LS adds a memory layer above those workflows: successful routes become reusable
trails, weak routes decay, and useful contributors build reputation through
auditable outcomes.
```

## What To Build Next

1. Add a CI validator for `examples/trails/*.json` against `schemas/cognitive_trail_run.schema.json`.
2. One-command demo runner.
3. GitHub PR review trail demo.
4. Best-route replay report.
5. Contribution and route dashboard.
6. External model/agent adapter so other agents can submit route outcomes.
7. MCP client examples for Codex, local Qwen, Claude Desktop, and CI bots.

The network starts local-first, then grows by accepting route artifacts from
more models, agents, and repositories.

## PR Review Trail Demo

The first applied demo uses GitHub pull-request review as the concrete route
memory use case:

```bash
python scripts/run_pr_review_trail_demo.py
```

The demo seeds a local route map with prior review outcomes, then asks LS which
route should handle the next similar PR review.

Expected result:

```text
Selected route: pr_review>local>gonka>mimo
Reason: goal-vector-cooperative
```

This is the practical product wedge:

```text
PR diff + CI evidence
-> learned review route
-> draft / critic / verifier
-> route reward
-> better default path next time
```
