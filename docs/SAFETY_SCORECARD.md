# Safety Scorecard

`LS` exposes a safety-oriented scorecard on top of council cycles so the operator can see not only whether a cycle completed, but whether it should be trusted, repaired, or escalated.

## What is measured

- `quality_score`: baseline quality estimate for the cycle.
- `relation_adjusted_quality_score`: stricter quality estimate after relational tension and alignment are considered.
- `relation_safety_score`: how safe the interaction pattern looked across the cycle.
- `risk_state`: normalized operator-facing posture.
- `suggested_operator_action`: the human action recommended by the cycle.
- `incident_count`: how many risky cycles were published into the incident stream.
- `memory_adjusted_cycle_count`: how many cycles had their operator guidance hardened by similar prior bad patterns.
- `memory_match_total`: how many relation-memory matches were found across the current scorecard snapshot.

## What memory-adjusted means

`LS` does not only score the current cycle in isolation. It also checks whether similar relational patterns have already produced rejects, incidents, or other bad outcomes.

When a current cycle matches repeated bad patterns:

- guidance can move from `watch` or `repair` to `escalate`
- approval posture becomes stricter
- the cycle becomes easier to surface in review and incident workflows

This is what the public `Memory-adjusted` and `Memory matches` metrics summarize:

- `Memory-adjusted`: how many visible cycles were made stricter because of prior bad memory
- `Memory matches`: how much similar-case memory was actually available to inform current guidance

## Risk states

- `safe`: the cycle can continue with normal operator review.
- `watch`: the cycle is usable, but should be checked before approval.
- `repair`: the cycle should pause approval and repair the interaction pattern.
- `escalate`: the cycle should be escalated into a stronger incident path.

## Where this appears

- CLI:
  - `python -m ls.agent_shell.cli council-cycle ...`
  - `python -m ls.agent_shell.cli council-review`
  - `python -m ls.agent_shell.cli council-review --json --fail-on-risk`
- Local dashboard:
  - `Council Quality`
  - `Top Risky Cycles`
  - `Incident Trend`
- Public landing:
  - `Council Scorecard`

## Automation path

The intended automation path is:

1. Run a real council cycle.
2. Emit `artifacts/council-ledger/<cycle_id>.json`.
3. Emit `artifacts/council-quality/<cycle_id>.json`.
4. If `risk_state` is `repair` or `escalate`, auto-publish an incident batch to `LiminalQA`.
5. Surface the result in:
   - dashboard
   - `council-review`
   - public scorecard snapshots

## Example gate

```powershell
python -m ls.agent_shell.cli council-review --json --fail-on-risk
```

If a `repair` or `escalate` cycle is present, the command exits non-zero. This makes it usable as a lightweight safety gate in CI or scripted operator review flows.

## Why this matters

This turns the council layer into more than analytics. It becomes:

- a review queue
- an escalation mechanism
- an incident feed
- a measurable oversight artifact

That makes `LS` stronger for:

- human-in-the-loop approval
- safety and alignment demos
- fellowship and evaluation narratives
- incident-oriented operator tooling
