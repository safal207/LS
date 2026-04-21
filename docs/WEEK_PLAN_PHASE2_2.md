# Week Plan: Phase 2.2

This document turns the current `Phase 2.2: Learning from Relations` priority into a 5-day execution plan.

The goal for the week is not to expand the surface area of `LS`.

The goal is to strengthen the product core so the relational layer:

- learns from outcomes,
- measures coherence,
- detects breaches early,
- and changes operator and safety behavior in a traceable way.

## Weekly Objective

By the end of the week, `LS` should be able to:

1. update relational edge strength from real cycle outcomes,
2. compute and expose `relational_coherence`,
3. detect relational breaches between conflicting high-priority routes,
4. surface these signals in artifacts, policy, and dashboard previews.

This week is focused on:

- `PR-A: Edge Strength Auto-Update`
- `PR-B: Relational Coherence v0`
- `PR-C: Council Relational Breach Detection v0`

## Day 1: PR-A Design and Integration Skeleton

### Goal

Define the update rule and integration points for adaptive relation strength.

### Work

- define bounded update inputs:
  - `review_decision`
  - `incident_published`
  - `receiver_resonance_score`
- define edge update outputs:
  - `strength_before`
  - `strength_after`
  - `reason_codes`
- identify the exact write path in:
  - `resonance_agent`
  - memory store
  - policy engine

### Primary files

- `python/modules/graph/memory_store.py`
- `python/modules/agent/resonance_agent.py`
- `python/modules/agent/relational_policy_engine.py`

### Acceptance criteria

- one deterministic update function is specified
- artifact fields are agreed and stable
- no graph mutation happens yet outside the planned update path

## Day 2: PR-A Implementation and Tests

### Goal

Make relation edges actually change from outcomes.

### Work

- implement bounded edge updates
- apply updates after cycle outcome is known
- persist edge-strength delta information in artifacts
- add tests for:
  - positive outcome
  - negative outcome
  - incident outcome
  - deterministic repeatability

### Acceptance criteria

- identical inputs produce identical strength updates
- edge updates are visible in artifacts
- targeted tests pass

## Day 3: PR-B Relational Coherence v0

### Goal

Add one global relational quality metric that policy can use.

### Work

- define and compute `relational_coherence` in the `0.0..1.0` range
- include coherence in:
  - `council-quality`
  - `relation-memory`
- surface coherence in dashboard preview
- add first policy use:
  - low coherence -> `validate_current_route` or escalation gate

### Primary files

- `python/modules/graph/relational_field.py`
- `python/modules/agent/relational_policy_engine.py`
- `tools/liminalqa_local_dashboard.py`

### Acceptance criteria

- coherence exists in artifacts
- coherence is visible in operator-facing preview
- policy rule hits can explain low-coherence behavior

## Day 4: PR-C Council Relational Breach Detection

### Goal

Detect when strong relational routes contradict each other and require stronger handling.

### Work

- define relational breach conditions
- detect conflict between high-priority routes
- emit `relational_breach` event payload
- make unresolved severe breach default to safe escalation
- expose breach status in council output

### Primary files

- `python/modules/agent/resonance_agent.py`
- coordination or council routing path
- dashboard preview or queue summary

### Acceptance criteria

- one reproducible fixture triggers a breach
- severe unresolved breach escalates safely
- breach rationale is visible in artifacts

## Day 5: Stabilization and Product Readiness

### Goal

Make the new relational behavior usable, explainable, and ready to show.

### Work

- verify `PR-A + PR-B + PR-C` together as one chain
- tighten dashboard wording and field naming
- update relevant safety or scorecard docs if needed
- produce one short reviewer-ready summary of:
  - what changed
  - what is now measured
  - what is now prevented earlier

### Acceptance criteria

- artifacts are internally consistent
- dashboard preview does not crash on empty or partial data
- the new behavior can be explained in one short product narrative

## Definition of Done for the Week

This week is successful when all of the following are true:

- relation edges update from outcomes automatically
- `relational_coherence` is computed and influences policy
- relational breaches are detected and can trigger escalation
- dashboard previews show the new signals
- targeted tests cover the three new behaviors

## What Not To Do This Week

Do not spend this week on:

- federation,
- portfolio control,
- major multimodal expansion,
- large branding passes,
- unrelated dashboard redesign.

Those are valid later steps, but they are not the highest-leverage product move right now.

## Product Rationale

At this point, `LS` already has:

- risk detection,
- review queues,
- incident routing,
- council quality,
- memory artifacts.

What it still needs most is:

- learning from outcomes,
- measuring relational stability,
- preventing bad routes earlier.

That is why this week should focus on:

- learning,
- coherence,
- breach detection.

Not on expanding new surfaces.
