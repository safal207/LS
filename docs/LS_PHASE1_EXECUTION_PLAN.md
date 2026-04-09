# LS Phase 1 Execution Plan

This document turns `Phase 1: Evaluation Core` from [LS_INTEGRATION_ROADMAP.md](LS_INTEGRATION_ROADMAP.md) into a concrete implementation checklist.

`Phase 1` is the `LiminalQA + CEL + CouncilContributionLedger` integration pass.

Its job is to make one `LS` council cycle measurable end-to-end:

- the council runs
- the ledger is emitted
- contribution and reputation are updated
- merit is updated
- evaluation data is published
- one combined artifact can be inspected and replayed

## Phase 1 Goal

After this phase, one real `LS` coordination cycle should produce a verifiable chain:

1. `ResonanceAgent` emits a `CouncilContributionLedger`
2. `CEL` turns that ledger into:
   - contribution records
   - reputation updates
   - merit updates
3. `LiminalQA` receives an evaluation payload for the same cycle
4. one combined artifact summarizes:
   - council outcome
   - evaluation outcome
   - contribution and merit effects
5. the dashboard and scorecard can show the result without manual stitching

## In-Scope Modules

### Core council and cognition

- [python/ls/cognition/council_contribution_ledger.py](../python/ls/cognition/council_contribution_ledger.py)
- [python/modules/agent/resonance_agent.py](../python/modules/agent/resonance_agent.py)

### Contribution, reputation, and merit

- [python/modules/cel/council_sync.py](../python/modules/cel/council_sync.py)
- [python/modules/cel/merit_sync.py](../python/modules/cel/merit_sync.py)
- [python/modules/cel/contribution_api.py](../python/modules/cel/contribution_api.py)
- [python/modules/cel/reputation_engine.py](../python/modules/cel/reputation_engine.py)

### Evaluation and visualization

- [tools/liminalqa_local_dashboard.py](../tools/liminalqa_local_dashboard.py)
- [tools/run_fellowship_demo.py](../tools/run_fellowship_demo.py)
- [tools/export_council_scorecard.py](../tools/export_council_scorecard.py)

### Reference docs

- [LIMINALQA_TEST_STRATEGY.md](LIMINALQA_TEST_STRATEGY.md)
- [CI_QUALITY_GATES.md](CI_QUALITY_GATES.md)
- [COUNCIL_CONTRIBUTION_LEDGER_ROADMAP.md](COUNCIL_CONTRIBUTION_LEDGER_ROADMAP.md)

## Deliverables

### 1. One combined council-quality artifact

Add a new artifact family:

- `artifacts/council-quality/<cycle_id>.json`

Each artifact should include:

- council ledger snapshot
- derived `quality_score`
- contribution summary
- reputation updates
- merit updates
- `LiminalQA` publish status
- any generated evaluation identifiers

This artifact is the main Phase 1 output.

## Suggested payload shape

```json
{
  "cycle_id": "uuid",
  "council_ledger_path": "artifacts/council-ledger/<cycle_id>.json",
  "quality_score": 0.84,
  "council_outcome": {
    "success": true,
    "selected_route": "route-a",
    "receiver_resonance_score": 0.78
  },
  "cel": {
    "contribution_records": [],
    "reputation_updates": [],
    "merit_updates": []
  },
  "liminalqa": {
    "published": true,
    "status_code": 200
  }
}
```

### 2. Unified council quality score

Keep the existing `quality_score_from_council_outcome(...)` in [council_sync.py](../python/modules/cel/council_sync.py) as the main Phase 1 derived metric.

Use that score everywhere Phase 1 needs one top-level number:

- council-quality artifact
- dashboard summary
- public scorecard export when available
- later benchmark notes

### 3. LiminalQA publish path for council cycles

Treat council cycles as evaluable observations, not only test lanes.

For each cycle, publish:

- one run packet
- one or more synthetic tests or facts
- signals for:
  - `quality_score`
  - `receiver_resonance_score`
  - `network_improvement`
  - `best_contributor_score`

Use the same discipline already described in [LIMINALQA_TEST_STRATEGY.md](LIMINALQA_TEST_STRATEGY.md):

- machine-readable payloads
- explicit artifacts
- reproducible replay path

### 4. Dashboard visibility

The local dashboard should be able to show:

- latest council-quality artifact
- latest `LiminalQA` publish result for a cycle
- latest `quality_score`
- latest best contributor and merit summary

This does not need a new full page.

It can start as:

- one extra API endpoint
- one summary block
- one link to the combined artifact

## Execution Order

### Step 1. Emit the combined artifact

Primary target:

- [python/modules/agent/resonance_agent.py](../python/modules/agent/resonance_agent.py)

Add a post-cycle write step that:

1. takes the emitted council ledger
2. calls `apply_council_ledger_to_cel(...)`
3. writes `artifacts/council-quality/<cycle_id>.json`

This should work even before `LiminalQA` publishing is added.

### Step 2. Add LiminalQA publishing for cycles

Primary targets:

- [tools/run_fellowship_demo.py](../tools/run_fellowship_demo.py)
- [tools/liminalqa_local_dashboard.py](../tools/liminalqa_local_dashboard.py)

Add one helper that transforms a council cycle into a `LiminalQA` ingest payload.

Start with:

- run metadata
- one synthetic evaluable item per cycle
- signals carrying council metrics

Then store the publish result back into the council-quality artifact.

### Step 3. Surface the artifact in the dashboard

Primary target:

- [tools/liminalqa_local_dashboard.py](../tools/liminalqa_local_dashboard.py)

Add:

- endpoint for latest `council-quality` summary
- optional button to publish the latest cycle to `LiminalQA`

### Step 4. Connect to demo and scorecard flow

Primary targets:

- [tools/run_fellowship_demo.py](../tools/run_fellowship_demo.py)
- [tools/export_council_scorecard.py](../tools/export_council_scorecard.py)

The one-command demo should refresh:

- council ledger
- council-quality artifact
- scorecard snapshot

The public scorecard should stay curated, but it should be able to read `quality_score` if present.

### Step 5. Add regression tests

Primary targets:

- `python/tests/test_*`

Minimum coverage for Phase 1:

- council cycle emits `council-quality` artifact
- `quality_score` is stable and bounded
- CEL sync is present in the artifact
- `LiminalQA` publish helper builds the expected payload
- dashboard endpoint returns the latest summary without crashing on empty state

## Acceptance Criteria

Phase 1 is complete when all of these are true:

- a real or dry-run council cycle writes:
  - `artifacts/council-ledger/<cycle_id>.json`
  - `artifacts/council-quality/<cycle_id>.json`
- the council-quality artifact contains:
  - `quality_score`
  - `contribution_records`
  - `reputation_updates`
  - `merit_updates`
- at least one path can publish cycle metrics to `LiminalQA`
- the local dashboard can display the latest council-quality summary
- the fellowship demo command refreshes the evidence path without manual file editing

## Verification Checklist

### Local verification

1. Run:

```powershell
python tools/run_fellowship_demo.py "Run a council coordination cycle for this operator request" --llm-mode auto
```

2. Confirm new files exist:

- `artifacts/council-ledger/<cycle_id>.json`
- `artifacts/council-quality/<cycle_id>.json`

3. Open the dashboard:

- `http://127.0.0.1:8090`

4. Confirm the dashboard shows:

- latest council cycle summary
- latest quality score
- latest best contributor

5. Confirm `LiminalQA` ingest receives the cycle payload if publishing is enabled.

### Test verification

Run targeted tests for:

- council artifact generation
- CEL sync
- dashboard summary endpoint
- scorecard export compatibility

## Risks to Watch

- `resonance_agent.py` is already a sensitive file with local worktree churn
- low-signal local LLM outputs can still produce weak route labels like `unknown`
- publishing noisy cycles to `LiminalQA` can pollute the evidence story if not tagged clearly
- public scorecard should keep preferring curated evidence over raw local churn

## Definition of Done

`Phase 1` is done when `LS` can show one council cycle as one coherent evidence object:

- who participated
- what was chosen
- how well it landed
- how CEL changed
- how merit changed
- whether evaluation was published

At that point `LS` stops looking like disconnected subsystems and starts looking like one measurable oversight runtime.
