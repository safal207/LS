# RFC: Relational Field Layer for LS

## Status
- **Author:** LS architecture working draft
- **Date:** 2026-04-03
- **Status:** Proposed (MVP track)

## Motivation
Current LS components reliably process explicit utterances and reasoning traces, but they do not yet model interaction dynamics as a first-class runtime object.

This RFC introduces a dedicated **Relational Field Layer** that separates:
1. Observable front-layer signals.
2. Hypothesized back-layer drivers.
3. Shared interaction-field state between participants.

Core design rule:

> **signal ≠ cause**

The system should never treat front behavior as proof of hidden motives.

## Goals
- Represent relationship state for dyadic and multi-party conversations.
- Infer hidden-state hypotheses with explicit uncertainty.
- Detect escalation loops (e.g., defense ↔ defense) before hard conflict.
- Select a stabilizing next move (repair policy), not only a content answer.
- Persist relational episodes for retrieval and future guidance.

## Non-goals
- Psychological diagnosis of participants.
- Claiming hidden motives as facts.
- Replacing explicit consent and safety controls.

## Conceptual model
Conflict and repair are modeled as:

- `conflict = hidden_background × front_expression × interaction_field_state`
- `repair = background_recognition + field_decompression + stabilizing_next_action`

## Data model

### InteractionFieldState
```python
@dataclass
class InteractionFieldState:
    field_id: str
    participants: list[str]

    shared_tension: float = 0.0
    shared_trust: float = 0.5
    support_gap: float = 0.0
    projection_risk: float = 0.0
    mutual_legibility: float = 0.5
    repair_readiness: float = 0.5

    dominant_theme: str | None = None
    active_misalignment: str | None = None
    recommended_mode: str | None = None
```

### BackLayerHypothesis
```python
@dataclass
class BackLayerHypothesis:
    participant_id: str
    fear_signal: float = 0.0
    overload_signal: float = 0.0
    belonging_need: float = 0.0
    control_need: float = 0.0
    validation_need: float = 0.0
    withdrawal_risk: float = 0.0
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
```

### FrontSignalFrame
```python
@dataclass
class FrontSignalFrame:
    participant_id: str
    speech_act: str | None = None
    tone: str | None = None
    interruption: bool = False
    withdrawal: bool = False
    escalation: float = 0.0
    softness: float = 0.0
    explicit_request: str | None = None
```

## Runtime pipeline
1. **Observe**: Gather front signals (text, timing, silence markers, optional multimodal cues).
2. **Infer carefully**: Build back-layer hypotheses with confidence + evidence.
3. **Compose field**: Update interaction field state.
4. **Detect pattern**: Classify dynamics:
   - normal_disagreement
   - projection_conflict
   - overload_spillover
   - hidden_need_mismatch
   - coalition_drift
   - silent_withdrawal
   - mutual_escalation
5. **Select repair mode**: Choose stabilizing action.
6. **Learn**: Save relational episode for retrieval.

## New engines and policies

### ProjectionDissonanceEngine
Purpose:
- detect projection pressure,
- detect front-only responses,
- detect closed escalation loops.

Example output:
```json
{
  "projection_risk": 0.82,
  "pattern": "back_pain_to_front_attack",
  "loop": [
    "participant_a_hidden_overload",
    "participant_a_front_irritation",
    "participant_b_defensive_response",
    "field_tension_growth"
  ],
  "repair_hint": "name_hidden_load_before_content"
}
```

### RelationalRepairPolicy
Candidate strategies:
- `validate_before_solve`
- `slow_down_exchange`
- `surface_hidden_need`
- `reduce_projection`
- `restore_shared_frame`
- `split_issue_from_state`
- `ask_for_explicit_need`

## Integration with existing LS pieces

### ResonanceKnowledgeUnit
Extend episode metadata to include:
- `field_state_before`
- `repair_action`
- `field_state_after`
- `projection_risk`
- `mutual_legibility`

### GraphMemoryRuntime
Add retrieval by relational patterns, e.g.:
- escalation due to unacknowledged overload,
- hidden-goal mismatch,
- form-vs-background misread.

Inject retrieval hints for next move selection.

### CareCycleRunner
Add relational review question:
- "Does this module generate high relational debt?"

Track:
- relational safety,
- repair capacity,
- projection sensitivity.

### Qwen Omni Worker
Use multimodal cues only as soft evidence:
- pauses,
- voice instability,
- verbal/affective mismatch.

Output language must remain probabilistic: "possible", "signals", "hypothesis", "needs clarification".

## Unified participant model
Use the same abstraction for human and agent participants.

Each participant has:
- visible signal,
- hidden-state hypothesis,
- role,
- load/pressure,
- goal vector,
- relation edges.

Graph edges:
- trust,
- tension,
- alignment,
- dependence,
- support,
- friction,
- projection pressure.

## Metrics
- `field_tension`
- `field_coherence`
- `mutual_legibility`
- `projection_risk`
- `support_gap`
- `repair_success_rate`
- `hidden_need_resolution_rate`
- `escalation_prevention_rate`
- `relational_resonance_score`

## MVP delivery plan

### MVP-1
- Add `InteractionFieldState` runtime object.
- Compute `shared_tension`, `mutual_legibility`, `projection_risk`, `recommended_mode`.
- Add helper: `suggest_relational_repair()`.

### MVP-2
- Persist relational episodes in `ResonanceKnowledgeUnit`.

### MVP-3
- Add relational-pattern retrieval and hint injection.

### MVP-4
- Extend care-cycle scoring with relational safety metrics.

## Safety constraints
- Hidden-state outputs are **hypotheses only**.
- All claims must include confidence and evidence traces.
- No hard statements about internal motives.
- Ask clarifying questions when confidence is low.

## Open questions
- Threshold calibration for projection risk under sparse signals.
- Multi-party attribution when two+ participants escalate simultaneously.
- Memory compaction strategy for high-volume relational episodes.
