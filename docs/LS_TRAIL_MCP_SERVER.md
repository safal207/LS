# LS Trail MCP Server v0.1

Status: **local-first experimental bridge**.

LS Trail MCP Server exposes the Cognitive Trail Network as a small MCP-facing
surface. The goal is to let Codex, local models, Claude/Kimi-style agents, or
future MCP clients connect to LS route memory without claiming that LS changes
their model weights.

```text
model output
-> contribution event
-> evidence check
-> human / CI / task outcome
-> route reward
-> reusable trail memory
```

## What This Gives Us

The value is not another model. The value is a shared memory of which
cooperative routes made work more precise.

```text
models answer
LS remembers which cooperation made the answer more precise
```

Over time, connected agents can ask LS which route to try, submit their local
contribution, and let LS update route memory only after evidence or outcome
signals exist.

## Current MCP Tools

| Tool | Purpose |
| --- | --- |
| `ls_trail_recommend_route` | Read local route memory and recommend a route for a task. |
| `ls_trail_submit_contribution` | Record an actor/role contribution as a pending local event. |
| `ls_trail_validate_evidence` | Estimate evidence coverage before a contribution is treated as useful. |
| `ls_trail_record_outcome` | Update route memory after human, CI, or evidence outcome signals. |
| `ls_trail_query_best_trails` | Return best known routes by repeatability score. |

## Current MCP Resources

| Resource | Purpose |
| --- | --- |
| `trail/routes` | Current route memory sorted by repeatability score. |
| `trail/events` | Recent local contribution and outcome events. |

## Safety Boundary

The v0.1 bridge is deliberately local-first:

- it does not update model weights;
- it does not call external services;
- it does not grant action authority;
- a contribution event does not update route score by itself;
- route memory is updated only through `ls_trail_record_outcome`;
- human authority remains required for action, memory, and reputation effects.

This keeps the network useful without pretending it is already a global live
intelligence layer.

## Minimal Flow

1. Ask for a route.

```json
{
  "action": "tools/call",
  "name": "ls_trail_recommend_route",
  "arguments": {
    "task_type": "pr_review",
    "available_backends": ["local", "gonka", "mimo"],
    "strategy_bias": "cooperative_reasoning"
  }
}
```

2. Submit a contribution.

```json
{
  "action": "tools/call",
  "name": "ls_trail_submit_contribution",
  "arguments": {
    "task_id": "pr-123",
    "route_key": "pr_review>local>gonka>mimo",
    "actor": "gonka",
    "role": "risk_critic",
    "evidence_refs": ["diff:src/app.py:42"],
    "note": "Found missing regression test."
  }
}
```

3. Validate evidence before learning from the contribution.

```json
{
  "action": "tools/call",
  "name": "ls_trail_validate_evidence",
  "arguments": {
    "claims": [
      {
        "claim": "Missing regression test",
        "evidence_refs": ["diff:tests/test_app.py"]
      }
    ]
  }
}
```

4. Record an outcome.

```json
{
  "action": "tools/call",
  "name": "ls_trail_record_outcome",
  "arguments": {
    "task_id": "pr-123",
    "route_key": "pr_review>local>gonka>mimo",
    "evidence_coverage": 0.9,
    "false_positive_rate": 0.05,
    "human_accepted": true,
    "ci_passed": true,
    "useful_findings": 3,
    "unsupported_claims": 0,
    "latency_ms": 1200
  }
}
```

5. Query best trails.

```json
{
  "action": "tools/call",
  "name": "ls_trail_query_best_trails",
  "arguments": {
    "route_prefix": "pr_review",
    "limit": 5
  }
}
```

## Storage

Default local paths:

```text
data/graph_memory/routes.json
data/graph_memory/trail_mcp_events.jsonl
```

Environment overrides:

```text
GRAPH_TRAIL_STORE_PATH
LS_TRAIL_MCP_EVENTS_PATH
```

These files are local runtime artifacts and are ignored by git.

## Why This Matters

This is the first concrete adapter shape for the cooperative precision network:

```text
external agents can connect
-> contribute to a route
-> receive evidence feedback
-> update local route memory after outcome
-> make the next similar task start from a better known path
```

The claim stays narrow:

```text
LS does not make models globally smarter.
LS makes repeated cooperation more precise by remembering verified routes.
```
