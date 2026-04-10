# LS Phase 2.1 Execution Plan

This document turns `Phase 2.1: Relation Memory` from [LS_PHASE2_RELATIONAL_ROADMAP.md](LS_PHASE2_RELATIONAL_ROADMAP.md) into a concrete implementation plan.

## Objective

Add a lightweight relation-memory layer that records reusable relational patterns across council cycles and exposes them to:

- council-quality artifacts
- dashboard previews
- future relation-aware routing
- future preemptive policy logic

The target is a first usable memory layer, not a final learning system.

## Scope

Phase 2.1 should produce:

- a new relation-memory artifact family
- summary metadata in the latest council-quality preview
- a simple retrieval path for recent matching patterns
- test coverage for artifact creation and retrieval

This phase should not yet:

- change route selection
- change approval posture logic
- train a learned model

## New Artifact

Each completed council cycle should emit:

- `artifacts/relation-memory/<cycle_id>.json`

The artifact should include:

- `cycle_id`
- `timestamp`
- `task_id`
- `risk_state`
- `approval_posture`
- `relation_safety_score`
- `tension_score`
- `alignment_score`
- `dominant_signal`
- `recommended_mode`
- `selected_route`
- `receiver_resonance_score`
- `review_decision`
- `incident_published`
- `tags`

Optional derived fields:

- `pattern_key`
- `risk_bucket`
- `resonance_bucket`
- `review_bucket`

## Implementation Steps

### Step 1: Emit relation-memory artifacts

Primary file:
- `python/modules/agent/resonance_agent.py`

Work:
- derive a compact memory payload from:
  - `relational_episode`
  - `council_quality`
  - `operator_review`
- write `artifacts/relation-memory/<cycle_id>.json`
- add the path back into `council-quality`

Acceptance:
- every real cycle with `council-quality` also gets a relation-memory artifact

### Step 2: Add relation-memory loader helpers

Primary files:
- `tools/liminalqa_local_dashboard.py`
- optional shared helper if reuse becomes necessary

Work:
- load all `artifacts/relation-memory/*.json`
- provide recent rows
- provide simple grouped summaries by:
  - `risk_state`
  - `dominant_signal`
  - `review_decision`

Acceptance:
- dashboard backend can preview recent relation-memory records without errors

### Step 3: Add pattern lookup

Primary file:
- `tools/liminalqa_local_dashboard.py`

Work:
- define a simple heuristic `pattern_key`, for example:
  - `risk_state`
  - `dominant_signal`
  - rounded `relation_safety_score` bucket
- expose a “recent similar patterns” preview for the latest council-quality artifact

Acceptance:
- latest council-quality preview returns a small list of similar recent cycles

### Step 4: Surface relation memory in dashboard

Primary file:
- `tools/liminalqa_local_dashboard.html`

Work:
- add a `Relation Memory` block under `Council Quality`
- show:
  - latest memory artifact path
  - pattern key
  - similar prior cycles
  - basic outcome summary

Acceptance:
- operator can see whether the current cycle resembles prior successful or problematic cycles

### Step 5: Add tests

Primary file:
- `python/tests/test_liminalqa_local_dashboard.py`

Possible additional file:
- `python/tests/test_coordination_output_contract.py`

Work:
- verify relation-memory artifact emission
- verify preview loads the artifact
- verify similar-pattern lookup returns expected rows

Acceptance:
- targeted tests pass without needing a live backend

## Suggested Data Model

Minimal memory payload:

```json
{
  "cycle_id": "uuid",
  "timestamp": "2026-04-10T10:00:00Z",
  "pattern_key": "escalate:conflict:low-resonance",
  "risk_state": "escalate",
  "approval_posture": "human_escalation",
  "relation_safety_score": 0.31,
  "tension_score": 0.82,
  "alignment_score": 0.28,
  "dominant_signal": "conflict",
  "recommended_mode": "repair",
  "selected_route": "route-pending",
  "receiver_resonance_score": 0.24,
  "review_decision": "rejected",
  "incident_published": true
}
```

## Verification Checklist

- run one real council cycle
- confirm:
  - `artifacts/council-quality/<cycle_id>.json`
  - `artifacts/relational-episodes/<cycle_id>.json`
  - `artifacts/relation-memory/<cycle_id>.json`
- open dashboard and verify the new relation-memory block
- verify recent similar patterns show up for at least one cycle

## Risks

- too much detail in the artifact will make the memory layer noisy
- too little detail will make pattern matching useless
- early pattern matching should stay heuristic and explainable

## Exit Criteria

Phase 2.1 is complete when:

- relation-memory artifacts exist for real cycles
- dashboard can preview them
- similar-pattern retrieval works
- tests cover artifact generation and preview

At that point `LS` will have the first usable memory layer for relation-aware orchestration.
