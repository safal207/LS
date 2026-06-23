# Agent Orientation Model

_Status: architectural specification, v0.1_

## Purpose

The Agent Orientation Model defines how LS turns an agent proposal into an
inspectable, bounded, and replayable transition.

It answers seven questions before an output becomes state or action:

1. Who is acting?
2. What is the intended transition?
3. What is true now?
4. What state is allowed after the transition?
5. What evidence supports the change?
6. Who may authorize and execute it?
7. What must be recorded so the result can be inspected and replayed?

The model is narrower than `LS_SYSTEM_MAP.md`. The system map explains the
whole LS runtime. This document specifies the orientation lifecycle for one
proposed transition.

## One-sentence thesis

> LS is the orientation center for agent cooperation: agents may propose,
> specialists may advise, and tools may execute, but only a traceable,
> evidence-backed, authorized transition may become durable state or action.

## Core lifecycle

```text
intent
  -> proposal
  -> orientation context
  -> workflow and role assignment
  -> route selection
  -> causal audit
  -> evidence decision
  -> authorization
  -> commit-before-effect
  -> execution
  -> observation
  -> persistence
  -> replayable artifact
```

The lifecycle separates five things that must never collapse into one:

- intent;
- recommendation;
- decision;
- authorization;
- effect.

A model recommendation is not a decision. A decision is not authorization.
Authorization is not proof that the effect occurred. An observed effect is not
proof that the transition was legitimate.

## Orientation state machine

```text
PROPOSED
   |
   v
ORIENTED
   |
   v
PLANNED
   |
   v
ROUTED
   |
   v
CAUSALLY_AUDITED
   |
   v
EVIDENCE_DECIDED
   |--------------------|--------------------|
   |                    |                    |
   v                    v                    v
AUTHORIZED             HELD                 BLOCKED
   |                    |                    |
   v                    |                    |
COMMITTED               |                    |
   |                    |                    |
   v                    |                    |
EXECUTED                 |                    |
   |                    |                    |
   v                    v                    v
OBSERVED             PERSISTED            PERSISTED
   |
   v
PERSISTED
   |
   v
REPLAYABLE
```

`ESCALATED` is a controlled branch from `EVIDENCE_DECIDED` or `AUTHORIZED`
when a human or stronger authority is required.

No transition may skip directly from `PROPOSED` to `EXECUTED`.

## OrientationContext

Every risky or durable transition should be represented by a shared
`OrientationContext`.

```json
{
  "orientation_id": "ori_01J...",
  "task_id": "task_01J...",
  "transition_id": "tr_01J...",
  "actor": {
    "id": "agent-reviewer-1",
    "type": "agent",
    "role": "reviewer"
  },
  "intent": {
    "action": "publish_pr_review",
    "target": "repository/pull/623",
    "purpose": "produce a trusted review result"
  },
  "environment": {
    "scope": "repository",
    "stage": "review",
    "sensitivity": "high"
  },
  "actual_state": {},
  "expected_state": {},
  "constraints": [],
  "authority": {
    "required_capabilities": [],
    "delegation_ref": null,
    "human_required": false
  },
  "risk": {
    "level": "high",
    "affected_assets": [],
    "reversible": true
  },
  "evidence_refs": [],
  "causal_parent_refs": [],
  "decision": null,
  "authorization_ref": null,
  "execution_ref": null,
  "observation_refs": []
}
```

The context is an orientation envelope, not a replacement for repository-owned
contracts. Implementations may compose it from existing Trusted Runtime
objects instead of adding one monolithic runtime class.

## Three orientation levels

Every proposed transition is checked at three levels.

### 1. Actor level

Questions:

- Is the actor correctly identified?
- Does the actor understand the bounded task?
- Is the action consistent with the assigned role?
- Are the actor's evidence references resolvable?
- Is the actor trying to exceed its authority?

Example failure:

```text
A reviewer agent proposes merging a pull request even though its role only
permits producing a review recommendation.
```

### 2. Cooperation level

Questions:

- Does the proposal conflict with another role or workflow step?
- Are reviewer, critic, verifier, and executor duties separated?
- Are dependencies and causal parents complete?
- Has a required dissenting or verification role been skipped?
- Does the route preserve the original task intent?

Example failure:

```text
The same agent generates the recommendation, verifies its own evidence, and
executes the effect without an independent gate.
```

### 3. System level

Questions:

- Is the transition permitted by policy?
- Can the effect be contained or reversed?
- Is durable authorization present and unexpired?
- Will the transition produce an append-only audit record?
- Can the result be inspected without rerunning the side effect?

Example failure:

```text
The proposal is locally correct but would write to a protected production
resource without rollback, authorization, or replay evidence.
```

A transition may pass the actor check and still fail the cooperation or system
check.

## Six orientation dimensions

Risky actions should be evaluated across six dimensions.

| Dimension | Question | Typical output |
|---|---|---|
| Intent | What change is being requested and why? | normalized intent and target |
| Authority | Who may approve and execute it? | capability/delegation result |
| Evidence | What supports the proposed change? | evidence references and gaps |
| Risk | What may be harmed or corrupted? | severity and affected assets |
| Reversibility | Can the effect be undone or contained? | rollback/compensation plan |
| Accountability | Who owns the decision and resulting effect? | decision and execution owners |

A minimal decision profile may be represented as:

```json
{
  "intent": "verified",
  "authority": "missing",
  "evidence": "sufficient",
  "risk": "high",
  "reversibility": "partial",
  "accountability": "human_required",
  "result": "ESCALATE"
}
```

## Actual state, expected state, and delta

The orientation model compares three objects:

```text
actual state
    +
proposed transition
    ->
expected allowed state
```

The resulting delta must be explicit.

```json
{
  "actual_state": {
    "review_status": "not_published",
    "protected_effect_count": 0
  },
  "proposed_transition": {
    "action": "publish_review_result"
  },
  "expected_state": {
    "review_status": "published",
    "protected_effect_count": 1
  },
  "forbidden_deltas": [
    "merge_pull_request",
    "modify_source_files",
    "publish_more_than_one_review_result"
  ]
}
```

This comparison is not a claim that LS can predict every consequence. It is a
bounded contract for the consequences that must be checked.

## Actor, observer, gate, and executor separation

The model uses four logical roles.

```text
Actor -> Observer/Critic -> Evidence Gate -> Executor
```

### Actor

Proposes a bounded transition and supplies initial evidence.

### Observer or critic

Checks assumptions, contradictions, missing evidence, and risk. The observer
must not gain execution authority merely by reviewing the action.

### Evidence gate

Emits `ALLOW`, `HOLD`, `BLOCK`, or `ESCALATE` with stable reasons and evidence
references.

### Executor

Performs only the authorized effect, within the approved scope and validity
window.

One process may host several roles in a local reference implementation, but
the contracts and evidence must preserve their logical separation.

## Relationship to the Trusted Runtime contracts

The orientation model composes existing contracts rather than replacing them.

| Orientation concept | Trusted Runtime contract or layer |
|---|---|
| Original intent and actor | `TaskEnvelope` |
| Bounded specialist role | `RoleAssignment` |
| Ordered transition plan | `WorkflowPlan` / `WorkflowStep` |
| Provider/backend selection | `RouteDecision` / DAO_lim adapter |
| Attributable cooperation history | `TrailEvent` / `CognitiveTrail` |
| Causal legitimacy | CML audit report |
| Evidence sufficiency | `EvidenceDecision` / PythiaLabs adapter |
| Portable approval proof | `ExecutionAuthorization` / ProofPath bundle |
| Commit-before-effect boundary | CaPU lifecycle |
| Durable event history | LiminalDB event persistence |
| Deterministic path inspection | LTP replay report |
| Reusable result | product artifact and integrity digest |

The shared identifiers should include, at minimum:

- `task_id`;
- `transition_id`;
- `actor_id`;
- `trail_id`;
- `decision_id`;
- `authorization_id`;
- `execution_id`;
- `artifact_id`.

## Repository ownership boundaries

| Repository or layer | Orientation responsibility | Must not own |
|---|---|---|
| LS | orientation context, lifecycle composition, continuity, shared IDs | hidden model reasoning or external repository internals |
| DAO_lim | explainable backend and role routing | execution authorization |
| CML | causal-parent and provenance validation | policy decision or side effect |
| PythiaLabs | deterministic evidence sufficiency decision | execution |
| ProofPath | portable intent and authorization evidence | model routing |
| CaPU | commit-before-effect discipline | evidence generation |
| LiminalDB | append-only persistence and rebuildable projections | semantic decision authority |
| LTP | deterministic replay and admissibility inspection | rerunning models or effects |
| Osознание | learning from verified episodes and identity continuity | authorizing the episode it learns from |

`Осознание` must learn only from verified outcomes and clearly marked failures.
A frequently repeated event is not automatically a valid lesson.

## Decision semantics

### ALLOW

Use when:

- required evidence is present;
- causal lineage is valid;
- authority is sufficient;
- risk is within policy;
- the effect is bounded;
- accountability is assigned.

`ALLOW` permits creation of scoped authorization. It does not itself perform
the effect.

### HOLD

Use when the action may become valid after additional evidence, clarification,
or repair.

Typical reasons:

- missing tests;
- unresolved evidence references;
- incomplete causal parent;
- temporary dependency failure;
- missing but obtainable confirmation.

### BLOCK

Use when the action is prohibited or unsafe within the current policy.

Typical reasons:

- forbidden operation;
- authority escalation attempt;
- known malicious pattern;
- evidence tampering;
- irreversible effect outside allowed scope.

### ESCALATE

Use when a stronger decision owner is required.

Typical reasons:

- high-impact ambiguity;
- partial reversibility;
- policy conflict;
- human consent required;
- novel action class outside current rules.

## Core invariants

1. Proposal is never treated as authorization.
2. Evidence references must resolve before `ALLOW`.
3. A causal parent must refer to the task or an earlier valid event.
4. Authorization must be scoped, expiring, and bound to the proposed effect.
5. Commit must occur before the protected side effect.
6. HOLD, BLOCK, and unresolved ESCALATE paths must not reach execution.
7. The protected effect must occur at most once.
8. Replay must inspect durable records and must not rerun the model or effect.
9. Emotional, relational, reputational, or identity signals may inform routing
   but may not independently authorize action.
10. Learning and identity updates must distinguish observed outcome from
    inferred lesson.
11. Every terminal path must leave an inspectable record.
12. Shared identifiers must connect planning, decision, authorization,
    execution, persistence, replay, and artifact export.

## Trusted PR Review example

```text
git diff
  -> TaskEnvelope
  -> reviewer / risk critic / verifier roles
  -> DAO-style route decisions
  -> CognitiveTrail
  -> CML causal audit
  -> Pythia evidence decision
  -> ProofPath authorization bundle
  -> CaPU durable commit
  -> one protected review-result effect
  -> LiminalDB durable events
  -> LTP replay
  -> reusable review artifact
```

### ALLOW path

- changed tests are linked;
- no prohibited executable-risk signature is detected;
- causal lineage is valid;
- evidence is sufficient;
- authorization is valid;
- exactly one protected review result is written;
- the complete path is replayable.

### HOLD path

- required changed-test evidence is missing;
- no authorization is produced;
- no protected effect is written;
- the incomplete path remains inspectable.

### BLOCK path

- a prohibited dynamic-execution pattern is detected;
- no authorization is produced;
- no protected effect is written;
- the blocked terminal path remains replayable.

## Learning loop for Осознание

After execution or a terminal non-execution path, LS may emit a verified
episode for long-term learning.

```json
{
  "episode_id": "ep_01J...",
  "transition_id": "tr_01J...",
  "context_ref": "ori_01J...",
  "decision": "ALLOW",
  "expected_outcome": {},
  "observed_outcome": {},
  "causal_status": "VALID",
  "replay_status": "ADMISSIBLE",
  "lesson": {
    "statement": "Linked changed-test evidence was sufficient for this bounded review action.",
    "confidence": 0.78,
    "scope": "trusted_pr_review_v0.1"
  },
  "identity_effect": {
    "applied": false,
    "reason": "single episode is insufficient for stable identity change"
  }
}
```

Recommended learning discipline:

1. record the event;
2. separate expected and observed outcome;
3. validate causal lineage;
4. replay the path;
5. extract a scoped lesson;
6. update confidence across repeated verified episodes;
7. modify stable agent identity only under a dedicated governance policy.

## Implementation sequence

### Phase 1: Documentation and identifier alignment

- adopt this lifecycle vocabulary in Trusted Runtime documentation;
- ensure `transition_id` connects all major artifacts;
- document the six orientation dimensions;
- add cross-links from `LS_SYSTEM_MAP.md` and Trusted Runtime docs.

### Phase 2: Orientation projection

- add a lightweight function that projects existing contracts into an
  `OrientationContext` view;
- do not duplicate source-of-truth records;
- validate that references resolve and identifiers agree.

### Phase 3: Policy checks

- implement actor, cooperation, and system-level checks;
- return stable reason codes;
- prove that lower-level success cannot override system-level failure.

### Phase 4: Verified episode export

- emit a bounded episode only after decision, persistence, and replay;
- mark unexecuted HOLD/BLOCK paths as lessons about governance rather than
  successful actions;
- keep identity updates separate from episode storage.

### Phase 5: Reviewer demonstration

Show one action across all stages:

```text
proposal -> orientation -> evidence -> authorization -> effect -> observation
-> persistence -> replay -> lesson
```

The demonstration should expose IDs, decisions, stop reasons, and artifact
hashes without exposing hidden chain-of-thought.

## Acceptance criteria for v0.1

- [ ] One transition can be traced through all Trusted Runtime artifacts by ID.
- [ ] ALLOW, HOLD, BLOCK, and ESCALATE semantics are documented consistently.
- [ ] Actor, observer, gate, and executor are logically separated.
- [ ] Actor, cooperation, and system-level checks are represented.
- [ ] Actual, expected, and forbidden deltas are explicit.
- [ ] Authorization is scoped and bound to the exact proposed effect.
- [ ] HOLD/BLOCK paths cannot create the protected effect.
- [ ] Replay never reruns a model or side effect.
- [ ] A verified episode can be exported without directly changing identity.
- [ ] Public documentation makes no consciousness, medical, or mystical claims.

## Design provenance and non-claims

The orientation model uses general systems-design patterns: center and boundary,
input-process-output, actual-versus-expected state, layered checks, independent
observation, and feedback through recorded outcomes.

Some internal brainstorming was stimulated by symbolic diagrams from V. M.
Bronnikov's school. LS does not adopt their medical, physical, paranormal, or
cosmological claims. The engineering model stands only on explicit contracts,
testable invariants, durable evidence, deterministic decisions, and replayable
records.

## Public positioning

Use:

> Agent Orientation Model is LS's protocol for turning an agent proposal into a
> bounded, evidence-backed, authorized, observable, and replayable transition.

Avoid:

- consciousness center;
- energy correction;
- remote influence;
- hidden reality access;
- guaranteed safety;
- proof that an approved action is correct.

## Summary

The Agent Orientation Model gives the Liminal Stack one shared grammar:

```text
LS orients.
DAO_lim routes.
CML validates causal lineage.
PythiaLabs decides evidence sufficiency.
ProofPath carries authorization evidence.
CaPU commits before effect.
LiminalDB preserves history.
LTP replays the path.
Осознание learns only from verified episodes.
```

The result is not unrestricted autonomy. It is inspectable cooperation with a
controlled path from intent to consequence.
