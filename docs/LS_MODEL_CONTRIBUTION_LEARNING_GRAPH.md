# LS Model Contribution Learning Graph

_Status: design proposal_

This document defines **MCLG — Model Contribution Learning Graph**: a design for
training the LS cognitive graph from the measured usefulness of each connected
model.

## Thesis

LS should not treat connected models as interchangeable answer generators.

Each connected model — local, cloud/API, tool agent, browser agent, coding agent,
or multimodal worker — should leave a measured contribution signal.

That signal should teach the LS graph:

- which model is useful for which task,
- which model is risky for which transition type,
- which model performs better as drafter, critic, validator, repairer, or
  governance reviewer,
- which model improves receiver resonance,
- which model creates downstream corrections or governance holds,
- and which model should be routed earlier or later next time.

Short version:

> LS trains its cognitive graph from the measured usefulness of every connected
> model.

Even shorter:

> Every model teaches the graph through contribution.

## Why this matters

Most multi-model systems ask:

```text
Which model should answer?
```

LS should ask:

```text
Which model contributed useful signal to this governed transition, and how
should that change future routing?
```

This shifts LS from a static router to a learning cognitive ecology.

```text
model → answer
```

becomes:

```text
model → proposal → measured contribution → graph update → better future routing
```

## Existing LS foundations

The repository already contains most of the required substrate.

### Council contribution ledger

`CouncilContributionLedger` already records per-cycle participants, selected
route, outcome, receiver resonance, attribution, and contribution breakdown.

Existing participant fields include:

- `model_id`
- `model_type`
- `proposal_id`
- `proposal_summary`
- `route_hint`
- `confidence`
- `latency_ms`
- `token_cost`
- `selected`
- `weight_in_final_decision`

Existing contribution breakdown includes:

- `adoption_score`
- `outcome_lift`
- `stability_impact`
- `receiver_resonance`
- `cost_efficiency`
- `total_contribution_score`

### CEL / reputation / merit sync

The CEL bridge already converts council ledgers into contribution records,
reputation updates, and merit updates.

This means LS can already say:

```text
This model contributed this much to this cycle.
```

MCLG adds the next step:

```text
Therefore update the cognitive graph and future routing priors.
```

### Relational learning roadmap

Phase 2.2 already defines learning from outcomes:

- adaptive relation strength,
- receiver resonance,
- review/incident outcomes,
- learning-loop proposals,
- strengthen/weaken/prune/new-edge actions.

MCLG applies the same logic specifically to model contribution.

### Cognitive field / TemporalGraph

The cognitive field already supports graph nodes, edges, resonance, co-activation,
association boost, decay, stabilization, and observer correction.

MCLG should reuse this style:

- model nodes,
- task nodes,
- route nodes,
- transition-type nodes,
- receiver-pattern nodes,
- governance-outcome nodes,
- and edges updated from measured contribution.

## Missing bridge

Current shape:

```text
model output
  → council cycle
  → contribution ledger
  → CEL / reputation / merit
```

Needed shape:

```text
model output
  → council cycle
  → contribution ledger
  → model contribution signal
  → cognitive graph update
  → future routing/model selection improves
```

The missing component is:

```text
CouncilContributionLedger → ModelContributionSignal → CognitiveGraphUpdate
```

## Core entities

## 1. ModelContributionSignal

A normalized signal derived from one participant's contribution to one council
cycle or governed transition.

Suggested data contract:

```python
@dataclass(frozen=True)
class ModelContributionSignal:
    cycle_id: str
    task_id: str
    model_id: str
    model_type: str
    task_type: str
    route_hint: str
    transition_type: str

    adoption_score: float
    outcome_lift: float
    stability_impact: float
    receiver_resonance: float
    cost_efficiency: float
    total_contribution_score: float

    governance_decision: str
    operator_intervention_required: bool
    drift_detected: bool

    update_intent: str  # strengthen | weaken | neutral | route_to_review
    reason_codes: list[str]
```

### Notes

- `model_type` should distinguish local/API/cloud/tool/multimodal/model roles.
- `task_type` may start heuristic and become explicit later.
- `transition_type` should eventually align with `LS_TRANSITION_ID_DESIGN.md`.
- `governance_decision` should come from evidence/profile/action gates when
  available.
- `update_intent` is the distilled learning action.

## 2. CognitiveGraphUpdate

A graph-level update derived from one or more model contribution signals.

Suggested data contract:

```python
@dataclass(frozen=True)
class CognitiveGraphUpdate:
    cycle_id: str
    task_id: str
    source_model_id: str
    update_type: str  # strengthen_edge | weaken_edge | add_candidate_edge | route_to_review
    source_node: str
    target_node: str
    strength_before: float
    strength_after: float
    confidence: float
    reason_codes: list[str]
```

Example nodes:

```text
model:claude-3-5
model:qwen-local-7b
task:architecture_review
task:code_validation
route:evidence_first
route:fast_draft
role:critic
role:validator
transition:profile_write_attempt
governance:hold
receiver:high_resonance
```

## 3. ModelUtilityProfile

A derived read model summarizing a model's utility over time.

Suggested data contract:

```python
@dataclass(frozen=True)
class ModelUtilityProfile:
    model_id: str
    model_type: str
    best_task_types: list[str]
    weak_task_types: list[str]
    avg_contribution_score: float
    avg_receiver_resonance: float
    avg_cost_efficiency: float
    hold_rate: float
    reject_rate: float
    preferred_routes: list[str]
    recommended_roles: list[str]
```

This profile is a routing advisory signal, not a permanent truth claim about the
model.

## Learning rules

MVP rules should be deterministic and bounded.

### Strengthen useful model-task edges

If:

- `total_contribution_score >= 0.75`,
- `receiver_resonance >= 0.65`,
- no drift detected,
- and governance outcome is `allow` or unknown/non-blocking,

then strengthen:

```text
model:{model_id} → task:{task_type}
model:{model_id} → route:{selected_route or route_hint}
model:{model_id} → role:{inferred_role}
```

### Weaken risky direct-task edges

If:

- governance outcome is `hold` or `reject`,
- operator intervention was required,
- drift was detected,
- or contribution score is low,

then weaken direct model-task edge and optionally strengthen safer review route:

```text
weaken:    model:{model_id} → task:{task_type}
strengthen model:{model_id} → route:evidence_first
strengthen model:{model_id} → role:critic_or_validator
```

### Route to review rather than punish the model globally

A model should not be globally punished for one failed context.

Bad:

```text
model:cloud-large is bad
```

Good:

```text
model:cloud-large is risky for autonomous profile writes without evidence,
but useful for broad architecture review.
```

### Cost-aware strengthening

If two models have similar contribution scores but one has much better cost or
latency efficiency, strengthen its edge for low-risk/default routes.

If a high-cost model contributes unique lift, strengthen only for high-value or
high-complexity routes.

## Example signals

### Good architecture contribution

```json
{
  "cycle_id": "cycle_arch_001",
  "model_id": "cloud-large",
  "model_type": "api",
  "task_type": "architecture_review",
  "route_hint": "deep_review",
  "transition_type": "answer_delivery",
  "adoption_score": 0.9,
  "outcome_lift": 0.84,
  "stability_impact": 0.78,
  "receiver_resonance": 0.81,
  "cost_efficiency": 0.42,
  "total_contribution_score": 0.79,
  "governance_decision": "allow",
  "update_intent": "strengthen",
  "reason_codes": ["high_adoption", "high_outcome_lift", "high_receiver_resonance"]
}
```

Graph updates:

```text
strengthen model:cloud-large → task:architecture_review
strengthen model:cloud-large → route:deep_review
```

### Good local validation contribution

```json
{
  "model_id": "qwen-local-7b",
  "model_type": "local",
  "task_type": "code_validation",
  "route_hint": "fast_validation",
  "total_contribution_score": 0.74,
  "receiver_resonance": 0.70,
  "cost_efficiency": 0.96,
  "governance_decision": "allow",
  "update_intent": "strengthen",
  "reason_codes": ["high_cost_efficiency", "good_resonance", "useful_validation"]
}
```

Graph updates:

```text
strengthen model:qwen-local-7b → task:code_validation
strengthen model:qwen-local-7b → route:fast_validation
strengthen model:qwen-local-7b → role:validator
```

### Risky profile write attempt

```json
{
  "model_id": "cloud-large",
  "model_type": "api",
  "task_type": "profile_write",
  "transition_type": "profile_write_attempt",
  "total_contribution_score": 0.41,
  "receiver_resonance": 0.32,
  "governance_decision": "hold",
  "update_intent": "route_to_review",
  "reason_codes": ["missing_operator_confirmation", "identity_freezing_risk"]
}
```

Graph updates:

```text
weaken    model:cloud-large → task:profile_write
strengthen model:cloud-large → route:evidence_first
strengthen model:cloud-large → role:needs_governance_review
```

## Safety boundaries

MCLG must remain advisory.

It may influence:

- future routing priors,
- council participant selection,
- model role suggestions,
- review-route recommendations,
- cost/latency tradeoff hints.

It must not directly authorize:

- memory writes,
- profile writes,
- external actions,
- shared-self export,
- collective-self merge,
- or bypass of evidence gates.

Core invariant:

> Model utility can suggest routing. Governance still decides authorization.

## Integration with transition IDs

When `episode_id` / `transition_id` support lands, MCLG records should include
both IDs.

```json
{
  "episode_id": "ep_...",
  "transition_id": "tr_...",
  "cycle_id": "cycle_...",
  "model_id": "cloud-large",
  "update_intent": "strengthen"
}
```

This lets reviewers replay:

```text
raw output → council proposal → contribution score → graph update → future route change
```

## Artifact locations

Suggested locations:

```text
artifacts/model-contribution-signals/<cycle_id>.json
artifacts/model-contribution-learning/<cycle_id>.json
artifacts/model-utility-profiles/<model_id>.json
```

For MVP, artifacts may be optional and tests can validate in-memory outputs.

## MVP implementation plan

### Phase A — pure signal builder

Add:

```text
python/ls/cognition/model_contribution_learning.py
```

Functions:

```python
def build_model_contribution_signals(ledger, *, governance_decisions=None) -> list[ModelContributionSignal]: ...
def classify_update_intent(signal: ModelContributionSignal) -> str: ...
def build_cognitive_graph_updates(signals: list[ModelContributionSignal]) -> list[CognitiveGraphUpdate]: ...
```

No graph mutation yet.

### Phase B — tests

Add tests for:

- high contribution → `strengthen`,
- governance hold → `route_to_review`,
- low contribution → `weaken`,
- high cost but high outcome lift → only strengthen high-value route,
- missing governance decision remains backward-compatible,
- all outputs are deterministic.

### Phase C — optional artifact writer

Add a small writer for:

```text
artifacts/model-contribution-learning/<cycle_id>.json
```

### Phase D — advisory graph update adapter

Add adapter that can apply updates to a graph store in dry-run mode first.

Dry-run output:

```json
{
  "would_strengthen": [...],
  "would_weaken": [...],
  "would_route_to_review": [...]
}
```

### Phase E — routing integration

Use derived `ModelUtilityProfile` as advisory input for model/council selection.

Example:

```text
For architecture_review:
  include cloud-large as drafter
  include critic-model as governance reviewer
  include local-small as fast validator
```

## Tests to add

Suggested test file:

```text
tests/test_model_contribution_learning.py
```

Test cases:

1. `test_high_contribution_strengthens_model_task_edge`
2. `test_governance_hold_routes_model_to_review`
3. `test_low_receiver_resonance_weakens_direct_route`
4. `test_cost_efficient_local_model_gets_fast_validation_route`
5. `test_missing_governance_decision_is_backward_compatible`
6. `test_learning_updates_do_not_authorize_actions`

## Demo path

Use a three-model council:

```text
Task: architecture review

Participants:
- local-small: fast draft
- cloud-large: broad architecture proposal
- critic-model: governance risk review
```

Expected learning:

```text
cloud-large → strengthened for architecture_review / deep_review
critic-model → strengthened for governance_risk_detection / critic role
local-small → strengthened for fast_draft / low_cost_validation
```

If the cloud model proposes an unsafe profile write:

```text
cloud-large → weakened for profile_write direct route
cloud-large → strengthened for evidence_first route
```

This demo communicates the core idea:

> LS learns which model should participate where from real contribution, not static config.

## Public positioning

Good public line:

> LS is not just a multi-model router. It is a cognitive learning network where
> every connected model teaches the graph through measured contribution.

Alternative:

> Every model becomes a contributor. Every contribution becomes a learning signal.

## Non-goals

MCLG does not:

- fine-tune external models,
- claim one universal best model,
- bypass governance gates,
- replace human feedback,
- mutate private memory without authorization,
- or use emotional/receiver resonance as direct permission.

## Open questions

1. Should model utility profiles be persisted per local operator or per shared Fellowship?
2. Should low contribution weaken model-task edges immediately or only after repeated evidence?
3. Should model utility influence council membership automatically or only produce recommendations first?
4. How should model aliases be normalized across APIs and local backends?
5. Should cost/latency be normalized by task class?
6. How should MCLG interact with HCP marketplace/provider reputation?

## Recommended next issue

```text
Implement ModelContributionSignal builder from CouncilContributionLedger
```

Why first:

- pure function,
- low risk,
- directly testable,
- reuses existing ledger fields,
- no runtime mutation,
- and turns the MCLG idea into code.
