# LS Phase 2.2 Execution Plan

This document translates the next post-`PR #402` milestone into an implementation-ready plan.

## Objective

Move relational memory from passive storage to an active learning system that:

- adjusts relation strength from outcomes,
- detects contradictions and weak links,
- proposes new links from multimodal context,
- and exposes explainable relational reasoning through MCP.

## Current Baseline (as of 2026-04-11)

Already available in `LS`:

- subconscious worker loop,
- resonance knowledge units,
- relation-memory persistence,
- MCP read-side observability,
- care-cycle and alignment reflection.

Phase 2.2 should build directly on this baseline without rewriting Phase 2.1 artifacts.

## Scope

Phase 2.2 includes five deliverables:

1. **Adaptive edge strength** (`strength` updates from feedback + outcomes).
2. **Relational Learning Loop** (background graph maintenance + proposals).
3. **Qwen3.5-Omni edge extraction hooks** (screen/audio context to relation candidates).
4. **`relational_coherence` metric** (consistency score across active thought graph).
5. **Council conflict awareness** (detect and surface relational breaches).

Out of scope for this phase:

- full autonomous policy rewrites,
- federation-wide shared cognition,
- irreversible deletion of historical memory without retention policy.

## Workstream A — Adaptive Relation Strength

Primary files:

- `python/modules/graph/memory_store.py`
- `python/modules/agent/resonance_agent.py`
- `python/modules/agent/relational_policy_engine.py`

Tasks:

- add edge update function that ingests:
  - user feedback polarity,
  - review decision,
  - incident outcomes,
  - receiver resonance score,
- implement bounded update rule (e.g., EMA + min/max clamp),
- record `strength_before`, `strength_after`, and reason codes in artifacts.

Acceptance criteria:

- every completed cycle with relational context can adjust at least one edge,
- updates are deterministic for identical inputs,
- strength history is auditable.

## Workstream B — Relational Learning Loop

Primary files:

- `python/modules/agent/resonance_agent.py`
- `python/modules/graph/relational_field.py`
- `tools/liminalqa_local_dashboard.py`

Tasks:

- introduce periodic learner pass (configurable interval),
- identify candidates for:
  - strengthening recurring successful patterns,
  - weakening unstable or contradictory patterns,
  - pruning stale low-value edges,
  - proposing new edges from repeated co-occurrence,
- emit learner artifacts in `artifacts/relational-learning-loop/`.

Acceptance criteria:

- learner runs without blocking primary response path,
- proposals include confidence + explanation,
- dashboard can show latest learner summary.

## Workstream C — Qwen3.5-Omni Relation Hooks

Primary files:

- `python/modules/agent/loop.py`
- `python/modules/agent/resonance_agent.py`
- `python/modules/intent/` (integration helper)

Tasks:

- consume multimodal observations (screen/audio-derived anchors),
- map anchors to existing memory units where confidence is above threshold,
- create candidate relational edges with provenance tags:
  - `source=omni_screen`
  - `source=omni_audio`
- route low-confidence candidates to review mode instead of auto-commit.

Acceptance criteria:

- multimodal relation candidates appear in artifacts,
- provenance is preserved end-to-end,
- low-confidence links are safely gated.

## Workstream D — Relational Coherence Metric

Primary files:

- `python/modules/graph/relational_field.py`
- `python/modules/agent/relational_policy_engine.py`
- `docs/SAFETY_SCORECARD.md`

Metric definition (initial):

- coherence should increase when high-strength edges agree on intent/risk direction,
- coherence should decrease when strong edges encode unresolved conflicts,
- output range: `0.0..1.0`.

Tasks:

- compute `relational_coherence` per cycle,
- include score in council-quality and relation-memory artifacts,
- add guardrails in policy engine for low-coherence states.

Acceptance criteria:

- metric is present in artifacts and dashboard previews,
- policy rules can reference coherence thresholds,
- score behavior is covered by unit tests for conflict/non-conflict cases.

## Workstream E — Council Relational Breach Detection

Primary files:

- `python/modules/agent/resonance_agent.py`
- `python/modules/agent/coordination/` (council integration)
- `docs/FELLOWSHIP_EVIDENCE_AUDIT.md`

Tasks:

- detect conflict when two high-priority relational routes disagree,
- emit `relational_breach` event with involved nodes/edges,
- require explicit council resolution path for severe breaches,
- log breach outcomes for downstream learning.

Acceptance criteria:

- breach detection triggers on reproducible conflict fixtures,
- council output includes conflict rationale,
- unresolved severe breach defaults to safe escalation.

## MCP 2.0 Bridge (Phase 2.2-Adjacent)

Plan interface additions after core learning loop is stable:

- `ask_relational_question(question)`
- `suggest_new_relation(source, target, rationale)`

Read-only MCP resources remain default until mutation safety checks are in place.

## 2–4 Week Delivery Sequence

1. **Week 1:** Adaptive edge strength + artifact extensions.
2. **Week 2:** Relational Learning Loop + dashboard preview.
3. **Week 3:** Council breach detection + coherence policy integration.
4. **Week 4:** Qwen3.5-Omni relation hooks + MCP interactive beta.

## Verification Checklist

- run targeted tests for relation strength updates,
- run council conflict fixture tests,
- validate learner artifacts are generated on schedule,
- confirm dashboard reads coherence + breach status,
- run a full end-to-end cycle with one multimodal relation proposal.

## Exit Criteria

Phase 2.2 is complete when:

- relation edges update from outcomes automatically,
- learner loop continuously proposes graph maintenance actions,
- coherence and breach states affect council/policy behavior,
- multimodal context can produce safe relation candidates,
- MCP has a clear path from observability toward interactivity.
