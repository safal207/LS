# LS Cognitive Trail Network

LS Cognitive Trail Network is the cooperative route-memory layer for AI co-work.

The core idea:

```text
Models do not only answer.
They leave trails.
LS remembers which trails worked.
```

Instead of treating every model call as a fresh isolated attempt, LS records the
route that produced a result: which roles participated, what quality signals
were observed, where the route needed repair, and whether the outcome was safe
to reuse. The next agent group can start from the best known route instead of
wandering from zero.

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

## What Exists Today

The repository already has the main building blocks:

- `python/modules/graph/cooperative_engine.py` coordinates role-based model routes.
- `python/modules/graph/path_selector.py` chooses routes using prior route stats.
- `python/modules/graph/trail_updater.py` computes route reward and updates `pheromone_weight`.
- `python/modules/graph/route_stats.py` stores route quality, runs, success count, and latency.
- `python/ls/cognition/council_contribution_ledger.py` records who contributed what.
- `docs/COOPERATIVE_MERITOCRACY_NETWORK.md` describes the broader cooperative model network.
- `docs/MERIT_LEDGER_CONSENSUS.md` describes merit and contribution consensus.

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

1. Route artifact schema for cognitive trails.
2. One-command demo runner.
3. GitHub PR review trail demo.
4. Best-route replay report.
5. Contribution and route dashboard.
6. External model/agent adapter so other agents can submit route outcomes.

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

## Real Git Diff Artifact

The next step is a local-first artifact builder that reviews a real git diff
instead of seeded sample data:

```bash
python scripts/run_pr_review_trail_artifact.py
```

By default it reviews the latest commit:

```text
HEAD~1..HEAD
```

For a branch or pull-request style range:

```bash
python scripts/run_pr_review_trail_artifact.py \
  --base origin/main \
  --head my-feature-branch \
  --output reports/pr_review_trail.json \
  --markdown-output reports/pr_review_trail.md
```

The artifact records:

- selected review route
- diff files and stat
- review signals
- route reward
- updated route memory
- human-facing review summary

This turns PR review into a reusable trail:

```text
real diff
-> draft reviewer / risk critic / evidence verifier / final reviewer
-> artifact
-> route reward
-> better default route for the next PR
```
