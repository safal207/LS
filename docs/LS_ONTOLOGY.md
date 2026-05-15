# LS Ontology

_Status: architecture vocabulary and boundary contract_

This document defines the core terms used across LS so that memory, relation,
emotion, governance, gateway, and Fellowship concepts remain distinct and
auditable.

The goal is not to make the system less ambitious. The goal is to make the
ambition legible.

## Core rule

> If a concept stores meaning, name what it stores. If it changes state, name who
> may update it. If it can affect action, name whether it is advisory or
> authoritative.

## Top-level ontology

| Term | Category | Stores / represents | Authority level |
|---|---|---|---|
| `Operator` | Human authority | The human user and their agency | Primary authority |
| `ExternalAgent` | Input source | Any model/tool/agent producing raw output | No authority by default |
| `PersonalAgentGateway` | Runtime boundary | How raw output becomes final output | Advisory/holding boundary |
| `ActionEvidenceGate` | Governance | Whether proposed action/write has enough evidence | Authoritative allow/hold/reject |
| `OperatorIdentityGovernance` | Governance | Identity/authorship/profile-boundary risk | Authoritative warning/hold input |
| `OperatorProfileWritePolicy` | Governance | Whether profile/memory writes are allowed | Authoritative write control |
| `CouncilCycle` | Coordination | Structured multi-agent deliberation event | Advisory unless governance allows |
| `CouncilContributionLedger` | Evaluation | Who contributed and what was adopted | Evidence/evaluation |
| `ReceiverResonance` | Evaluation | How cleanly result was accepted | Advisory/evaluation |
| `RelationalSelf` | Self-state | Current relation-aware system snapshot | Advisory state |
| `EmotionalMemory` | Memory | Inferred emotional tone events | Advisory memory |
| `EmotionalContinuity` | Continuity | Long-lived affective continuity over sessions | Advisory state |
| `AttachmentBond` | Continuity | Long-term bond stability and repair trajectory | Advisory state |
| `RelationalField` | Interpretation | Trust/tension/role/repair signals | Advisory context |
| `SharedRelationalSelf` | Sharing | Consented projection of self-state | Consent-bound projection |
| `CollectiveRelationalSelf` | Fellowship | Group-level merged relational state | Collective/advisory |
| `Fellowship` | Federation/social layer | Group membership, proposals, votes, reputation | Governance-mediated collective layer |
| `TraceArtifact` | Evidence | Replayable record of transition | Evidence layer |
| `Transition` | Core event | A governed state/output/action change | Must be traceable |

## Authority ladder

LS should maintain a strict authority ladder:

```text
Operator consent / explicit confirmation
        ↓
Governance and evidence gates
        ↓
Council proposals and quality signals
        ↓
Relational / emotional / attachment signals
        ↓
Raw model output
```

A lower layer may inform a higher layer, but it must not bypass it.

Example:

```text
warm emotional bond + missing operator confirmation = hold
high attachment + missing evidence = hold
strong council agreement + unsafe profile write = hold/reject
```

## Boundary table

| Concept | May inform routing? | May inform tone? | May write memory/profile? | May authorize action? |
|---|---:|---:|---:|---:|
| Raw model output | Yes | Yes | No | No |
| Gateway mode | Yes | Yes | No | No |
| Council outcome | Yes | Yes | No, unless gate allows | No, unless gate allows |
| Receiver resonance | Yes | Yes | No | No |
| RelationalSelf | Yes | Yes | No | No |
| EmotionalMemory | Yes | Yes | No | No |
| AttachmentBond | Yes | Yes | No | No |
| EmotionalContinuity | Yes | Yes | No | No |
| SharedRelationalSelf | Yes, if consented | Yes, if consented | No | No |
| CollectiveRelationalSelf | Yes, with provenance | Yes, with provenance | No | No |
| OperatorProfileWritePolicy | Yes | No | Yes | Yes for profile writes |
| ActionEvidenceGate | Yes | No | Yes | Yes |
| Operator explicit confirmation | Yes | Yes | Yes | Yes |

## Definitions

### Operator

The human whose agency, preferences, identity, and boundaries LS protects.

The operator is not a passive profile target. The operator is the primary
authority for persistent self/profile assumptions and external actions.

### ExternalAgent

Any model, script, tool, browser agent, coding agent, local LLM, cloud LLM, or
third-party system that produces output for LS to inspect.

External agents can propose. They do not own the operator's memory, profile, or
actions.

### PersonalAgentGateway

The runtime boundary between external agents and the operator.

It receives raw agent output and decides how that output should reach the
operator:

- `pass_through`
- `shape_response`
- `repair_before_send`
- `hold_or_escalate`

The gateway can shape and hold output, but it is not the final authority for
memory/profile/action writes unless paired with governance/evidence gates.

### ActionEvidenceGate

The deterministic checkpoint that decides whether a proposed action or state
write has sufficient evidence and permission.

It should evaluate:

- source evidence,
- operator confirmation,
- scope authorization,
- temporal permission,
- identity boundary risk,
- and replayable digest.

Outputs should be stable:

- `allow`
- `hold`
- `reject`

### OperatorIdentityGovernance

A governance signal that protects the operator from identity capture,
authorship confusion, or silent profile freezing.

It should warn or hold when an agent tries to:

- define the operator too permanently,
- write preferences without consent,
- decide on behalf of the operator,
- collapse temporary behavior into permanent identity,
- or cross authorship boundaries.

### OperatorProfileWritePolicy

The policy layer that controls writes into persistent operator profile or memory
state.

It should answer:

```text
May this proposed profile/memory update be stored?
```

Possible outcomes:

- allow,
- require confirmation,
- require continuity review,
- hold,
- reject.

### CouncilCycle

A structured decision round involving one or more models, agents, validators, or
internal roles.

A council can propose conclusions and provide evidence. A council result does
not automatically become authorized state or action.

### CouncilContributionLedger

The record of participant contribution, adoption, merit, and quality signals.

It answers:

- who contributed,
- what was adopted,
- what influenced the result,
- how contribution should affect reputation or merit.

### ReceiverResonance

A signal for how cleanly an output was received, accepted, or integrated.

Receiver resonance is not approval by itself. It is an evaluation signal.

### RelationalSelf

The current relation-aware self-state snapshot of LS.

It can include:

- coherence,
- core nodes,
- core edges,
- identity vector,
- change history,
- emotional summary,
- attachment facets.

It is a state snapshot, not an authority source.

### RelationalField

The interpretive layer for relation signals such as:

- trust,
- tension,
- role,
- proximity,
- repair,
- rupture,
- front/back/field dynamics.

It helps the system understand interaction context. It must not become a hidden
permission layer.

### EmotionalMemory

A set of inferred emotional memory entries derived from observable signals.

Typical fields:

- emotional tone,
- intensity,
- valence,
- confidence,
- bond strength,
- temporal decay,
- trigger source,
- relational context.

Correct framing:

> LS inferred a warm/supportive/tense tone from observable signals.

Incorrect framing:

> LS felt warm/supportive/tense.

### EmotionalContinuity

A persisted long-lived affective continuity state, usually computed from
emotional memory rows over time.

It helps LS restore relational affective context after restarts or long gaps.

It must be inspectable, resettable, and subordinate to operator consent.

### AttachmentBond

A modeled long-term bond state that tracks stability, repair, and trajectory
across interactions.

It is not a claim of human-style attachment. It is a bounded model of
relationship continuity.

Correct framing:

> modeled attachment-like continuity signal.

Incorrect framing:

> real attachment.

### SharedRelationalSelf

A consent-aware projection of RelationalSelf that can be shared with other LS
nodes or Fellowship participants.

It should preserve:

- consent mode,
- recipients,
- anonymization/projection boundaries,
- audit trail,
- revocation path.

### CollectiveRelationalSelf

A group-level representation produced by merging multiple member states under
Fellowship rules.

It must preserve member provenance and should never erase individual boundaries.

### Fellowship

The multi-user / multi-node social layer for shared groups, proposals, votes,
reputation, and collective relational state.

Fellowship is powerful because it lets multiple LS nodes form a collective
"we". It is risky if provenance, consent, and authority are weak.

### TraceArtifact

A replayable evidence artifact. It should capture the event, decision, or state
change with enough structure to inspect later.

Trace artifacts are the evidence surface of LS.

### Transition

The core event type LS should care about.

A transition is not merely that text was generated. A transition is that
something changed or tried to change:

- output became final answer,
- memory was written,
- profile was updated,
- action was allowed,
- council result was accepted,
- relational state shifted,
- shared self was projected,
- collective state was merged.

Future architecture should prefer a shared `transition_id` / `episode_id` across
all major artifacts.

## Term collisions to avoid

### EmotionalMemory vs AttachmentBond

EmotionalMemory stores event-level inferred affective signals.

AttachmentBond stores longer-lived bond trajectory.

Do not use them interchangeably.

### EmotionalContinuity vs RelationalSelf

EmotionalContinuity is affective continuity across time.

RelationalSelf is the current self-state snapshot.

EmotionalContinuity may contribute to RelationalSelf, but it is not the whole
self.

### SharedRelationalSelf vs CollectiveRelationalSelf

SharedRelationalSelf is an exported projection from one node/person/system.

CollectiveRelationalSelf is a group-level merged state.

Shared self requires consent. Collective self requires provenance.

### ReceiverResonance vs OperatorApproval

Receiver resonance indicates acceptance/fit.

Operator approval is explicit authorization.

A result can have high resonance and still lack authorization for a memory or
action write.

### CouncilAgreement vs ActionAuthorization

Council agreement is deliberative evidence.

Action authorization requires governance/evidence approval.

## Failure modes by term

| Concept | Failure mode | Guardrail |
|---|---|---|
| EmotionalMemory | Anthropomorphic overclaim | Always use inferred/signal-derived language |
| AttachmentBond | Manipulative overfitting | Reset/export/review; advisory-only use |
| RelationalSelf | Self-state becomes authority | Governance layer remains above it |
| SharedRelationalSelf | Private state leakage | Consent, anonymization, revocation |
| CollectiveRelationalSelf | Loss of individual provenance | Member-level provenance and audit |
| Gateway | Nice output bypasses policy | Evidence gate after/beside gateway |
| Council | Consensus mistaken for truth | Validators, evidence, replay, dissent tracking |
| ProfileWritePolicy | Silent identity freezing | Explicit confirmation and continuity review |
| ActionEvidenceGate | Over-permissive action | Stable stop reasons; deny by default when evidence missing |
| TraceArtifact | Fragmented evidence | Shared transition/episode ids |

## Preferred public language

Use:

- local-first oversight runtime,
- personal AI operating layer,
- governed agent gateway,
- replayable transitions,
- inferred emotional continuity,
- relation-aware memory,
- operator-controlled profile writes,
- evidence-gated actions,
- living cognition as inspectable continuity.

Avoid leading with:

- conscious AI,
- AI with feelings,
- artificial soul,
- autonomous selfhood,
- emotional manipulation,
- solved alignment,
- unrestricted agent autonomy.

## Canonical short descriptions

### Safety / research

LS is a local-first coordination and oversight runtime that turns model-assisted
decision cycles into replayable artifacts with contribution, resonance,
governance, and quality signals.

### Product

LS is a personal AI operating layer: agents pass through your memory,
governance, evidence, and relational context before they reach you.

### Vision

LS explores living cognition as inspectable continuity: memory, relation,
repair, authorization, and action evolving under operator governance.

## Implementation guidance

When adding a new subsystem, include this mini-contract in the PR description:

```text
Subsystem name:
Stores:
Updated by:
Reads from:
Writes to:
Authority level: advisory / evidence / authoritative
Can authorize action: yes/no
Can write profile/memory: yes/no
Reset/export path: yes/no
Trace artifact: yes/no
Main failure mode:
Guardrail:
```

This keeps new features from increasing conceptual entropy.

## Next ontology hardening

1. Add shared `transition_id` / `episode_id` across gateway, council, emotional,
   attachment, evidence, and Fellowship artifacts.
2. Add schema-version fields where missing.
3. Add reset/export controls for long-lived emotional and attachment state.
4. Add tests proving advisory layers cannot authorize writes/actions.
5. Add a diagram linking ontology terms to actual files/modules.
