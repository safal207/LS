# LS Conductor Quickstart

Status: **minimal developer quickstart for the first LS Conductor CLI wrapper**.

This quickstart shows the first product-facing LS Conductor surface:

```text
scripts/ls_conductor_review_pr.py
```

It is a local wrapper over existing LS PR-review and role-market artifacts. It is
not a hosted API, not a new agent framework, and not a rewrite of LS internals.

## One-Line Idea

```text
Send one PR diff. Get a cooperative route result with evidence, route score, and claim boundary.
```

## Run With a Saved Diff

From the repository root:

```bash
python scripts/ls_conductor_review_pr.py \
  --diff-file latest.diff \
  --policy cooperative_pr_review \
  --json
```

## Run Against a Git Range

```bash
python scripts/ls_conductor_review_pr.py \
  --base HEAD~1 \
  --head HEAD \
  --policy cooperative_pr_review \
  --json
```

## Write a JSON Artifact

```bash
python scripts/ls_conductor_review_pr.py \
  --base HEAD~1 \
  --head HEAD \
  --output reports/trails/conductor/pr_review.json \
  --json
```

## Human-Readable Output

Omit `--json`:

```bash
python scripts/ls_conductor_review_pr.py \
  --base HEAD~1 \
  --head HEAD
```

Expected summary shape:

```text
LS Conductor PR Review
Policy: cooperative_pr_review
Decision: review_with_conditions
Route: pr_review>draft_reviewer>risk_critic>evidence_verifier>final_reviewer
Route won vs single: true
Confidence: 0.82
Summary: ...
Claim boundary: ...
```

## JSON Fields

The first Conductor wrapper returns:

```text
artifact_type
conductor_version
task_type
policy
final_answer
route_id
route_score
confidence
route_won_vs_single
evidence
disagreements
signals
decision
cost_usd
latency_ms
artifact_path
source_artifact
role_market
claim_boundary
```

## What It Reuses

This wrapper intentionally reuses existing LS functions:

```text
build_pr_review_artifact(...)
build_pr_role_market_payload(...)
```

Source scripts:

```text
scripts/run_pr_review_trail_artifact.py
scripts/run_pr_role_market_demo.py
```

## Python SDK

Install the local SDK from the package directory:

```bash
python -m pip install -e python/ls_conductor
```

Then use it programmatically:

```python
from ls_conductor import LSConductor

ls = LSConductor()
result = ls.run(diff_file="latest.diff")

print(result.final_answer)       # human-readable summary
print(result.route_score)        # route score (0.0 - 1.0)
print(result.confidence)         # confidence (0.0 - 1.0)
print(result.route_won_vs_single)  # bool
print(result.evidence)           # list[Evidence]
print(result.decision)           # "review_with_conditions", etc.
```

The SDK is currently a local wrapper over the CLI. It does not call hosted model APIs by default.

### Healthcheck

```python
ls = LSConductor()
health = ls.healthcheck()
print(health.status)             # "ok" or "degraded"
print(health.available_backends) # ["local_cli", "run_pr_review_trail_artifact", ...]
```

### Compare

```python
ls = LSConductor()
result = ls.compare(
    candidates=["output A", "output B", "output C"],
    task="Review this PR for security risks",
)
print(result.winner)   # "candidate_1"
print(result.why)      # ["Candidate selected by heuristic scoring"]
```

### Output to file

```python
ls = LSConductor()
result = ls.run(
    diff_file="latest.diff",
    output="reports/conductor/review.json",
)
print(result.artifact_path)  # "/abs/path/to/review.json"
```

## What It Does Not Do Yet

The first wrapper does not provide:

```text
hosted API;
production auth;
live hosted model calls;
global model ranking;
formal proof of best answer;
formal Nash equilibrium.
```

## Claim Boundary

Keep this boundary visible:

```text
Conductor wrapper over LS PR-review route artifacts; not a formal proof of best answer or global model ranking.
```

## Next Step

The next product step is a local HTTP facade:

```text
POST /v1/conductor/run
GET /v1/health
```

But the current CLI is the first developer-facing handle:

```text
one diff -> cooperative PR-review route -> evidence-shaped JSON
```
