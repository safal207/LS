# Bronnikov → LS: Structural Patterns for Continuity, Orientation, and Experience

## Status

Design note / conceptual mapping for LS and Osaznanie.

This document does **not** adopt any unverifiable medical, physical, or metaphysical claims from Bronnikov’s materials. It extracts only **structural patterns** that may be useful for LS as an architecture of orientation, memory, verified experience, and continuity.

The goal is to translate those patterns into explicit LS modules, fields, and invariants.

---

## 1. Why this document exists

Some Bronnikov diagrams repeatedly organize human experience around:

- a **center of orientation** before action,
- multiple **signal channels** rather than one flat observation stream,
- a layered view of **individual → group → system**,
- temporal axes such as **past → present → future influence**,
- and a distinction between an event that **affects the person** and an event that may **reposition the person’s center**.

LS and Osaznanie already face equivalent design problems:

- how an agent should orient before action,
- how evidence from action outcomes should be typed and verified,
- how verified episodes should be retained without becoming self-authorizing,
- and how continuity / identity should evolve without being rewritten by a single event.

This note maps those structural patterns into LS.

---

## 2. Scope: what LS borrows and what it does not

### 2.1 LS borrows only structural patterns

LS may borrow the following architectural patterns:

1. **Orientation as a distinct stage before execution**
2. **Multi-layer representation of an event**
3. **Multiple evidence / signal channels**
4. **Individual → relational → system continuity levels**
5. **Time-structured experience: antecedent, observed outcome, eligible influence**
6. **Identity as a stable lattice of patterns, not a single summary blob**
7. **Not every experience may reposition identity**

### 2.2 LS explicitly does not borrow unverifiable claims

LS does **not** adopt:

- claims about subtle energy, biofields, or non-verified physiology;
- medical or neuroscientific claims without evidence;
- metaphysical claims presented as implementation truth;
- any authority claim derived from Bronnikov materials themselves.

This document is a **structural mapping only**.

---

## 3. Core mapping table

| Bronnikov structural pattern | LS equivalent | Possible LS location |
|---|---|---|
| Center of orientation before action | Orientation stack: TOC → RTOC → PATOC → OVC | `ls/centers/orientation/` |
| Multiple perception / signal systems | Typed evidence channels | `ls/centers/ovc/`, `VerifiedEpisode` evidence model |
| Individual → group → system layers | Continuity levels / governance levels | `scope_level`, `governance_level`, shared-memory policy |
| Past / present / future line | Antecedent → Observed → Eligible influence | `VerifiedEpisode` schema |
| Stable crystal / hologram-like self-structure | Identity lattice / continuity lattice | `ContinuityCoordinator`, identity aggregation |
| Event influences person but does not always redefine center | Experience candidate vs identity update separation | `VerifiedEpisode`, aggregation, identity proposal flow |

---

## 4. Pattern 1 — Center of orientation before action

### Structural idea

A repeated pattern in Bronnikov diagrams is that a person does not act directly from raw impulse. There is first a **center / position of orientation**, and only then perception, interpretation, decision, and action.

### LS equivalent

LS already decomposes this into orientation centers:

- **TOC** — temporal orientation of the individual agent
- **RTOC** — relational orientation: trust, delegation, handoff, consent continuity
- **PATOC** — precise action temporal orientation
- **OVC** — outcome verification after action

### LS design implication

Orientation must remain **a separate layer from permission and execution**.

The LS execution pipeline should preserve the rule:

```text
orientation -> candidate action -> authorization -> execution -> verification
```

not:

```text
memory/intent -> execute directly
```

### Proposed invariant

> An action may be considered for execution only after the agent has occupied a valid orientation position across time, relation, and precise action.

---

## 5. Pattern 2 — Multi-layer event model

### Structural idea

Events are not represented on one flat plane. A single event can have bodily, imaginal, interpretive, social, and temporal layers.

### LS equivalent

LS should treat each action episode as a multi-layer object.

### Proposed event layers in LS

#### Layer A — Orientation source

Where the action candidate came from:

- TOC / RTOC / PATOC results
- prior memory
- delegation / handoff / consent context

#### Layer B — Intended transition

What the agent expected to happen:

- `expected_transition_ref`
- `patoc_result_ref`
- expected side-effect / target-state transition

#### Layer C — Executed action

What was actually executed:

- action digest
- target
- actor
- parameters
- receipt / runtime trace

#### Layer D — Verified outcome

What independent verification says actually happened:

- `verification_result_digest`
- `observer_set_digest`
- `observer_independence_basis`
- `outcome_class`

#### Layer E — Experience retention

How the episode is retained:

- supporting / failure / contradicting evidence roles
- retention / redaction / expiry / supersession status

#### Layer F — Identity eligibility

Whether the episode is even allowed to participate in continuity / identity proposals.

### Design implication

A VerifiedEpisode must not collapse these layers into one flat memory item.

---

## 6. Pattern 3 — Multiple evidence / signal channels

### Structural idea

Human perception is modeled as if information comes from multiple channels, not from one undifferentiated stream.

### LS equivalent

Outcome verification should distinguish **evidence channels**, not just collect evidence blobs.

### Proposed LS evidence channel classes

- `actor_assertion` — what the actor claims happened
- `runtime_receipt` — what the tool / runtime / execution receipt says
- `target_observation` — what the affected target or environment shows
- `independent_observer` — what an observer independent of actor/tool confirms
- `relational_counterparty` — what the handoff / delegated counterparty confirms
- `human_confirmation` — what the human explicitly confirms

### Why this matters

Different actions require different channel mixes. A runtime receipt is not the same as an independent observer. A relayed group memory is not the same as a primary target observation.

### Design implication

OVC should be able to ask not only:

- is there evidence?

but also:

- which evidence channels are present?
- which are missing?
- which are dependent on each other?
- which conflict?
- which channels are mandatory for this action class?

### Possible schema direction

```json
{
  "evidence_channels": [
    {
      "kind": "runtime_receipt",
      "evidence_digest": "sha256:...",
      "independent": false
    },
    {
      "kind": "independent_observer",
      "evidence_digest": "sha256:...",
      "independent": true,
      "observer_independence_basis": "separate operator and target telemetry"
    }
  ]
}
```

---

## 7. Pattern 4 — Individual → relational → system continuity levels

### Structural idea

Human experience is often arranged in nested levels:

- the person,
- the group / relationship,
- the larger system.

### LS equivalent

LS should distinguish continuity and authority levels.

### Proposed continuity levels

#### Level 1 — Individual

Episode matters only to one agent’s own local continuity.

#### Level 2 — Relational / shared

Episode matters to multiple agents or to the agent-human relationship:

- delegation
- handoff
- consent continuity
- shared memory
- trust repair or trust break

#### Level 3 — System / governance

Episode may influence:

- shared norms
- durable policy
- continuity-wide identity proposals
- governance review

### Design implication

Not every VerifiedEpisode should be eligible for the same continuity consequences.

A local failure, a relational consent breach, and a system-worthy verified pattern should not enter the same pipeline with the same weight.

---

## 8. Pattern 5 — Time-structured experience

### Structural idea

Experience is often arranged not just as “an event happened”, but across temporal axes:

- what led into it,
- what happened now,
- what future it may influence.

### LS equivalent

Each VerifiedEpisode should be time-structured.

### Proposed three-part episode structure

#### A. Antecedent

What produced the episode:

- orientation result refs
- memory inputs
- delegation / consent / handoff context
- expected transition source

#### B. Observed

What was executed and what was verified:

- receipt
- target observation
- independent observers
- outcome class
- replay / contradiction / delayed consistency handling

#### C. Eligible influence

What the episode is allowed to affect:

- local lesson candidate
- shared-memory candidate
- identity proposal candidate
- policy / governance review candidate
- nothing (retain only as queryable history)

### Design implication

LS should not infer future influence from retention alone. Influence must be explicitly gated.

---

## 9. Pattern 6 — Identity as a lattice, not a blob

### Structural idea

The self is represented as a stable structure of interacting patterns, not as one isolated memory.

### LS equivalent

Identity should be represented as a **continuity lattice** rather than a single profile summary.

### Candidate identity tracks

- trust track
- relationship track
- competence track
- failure / recovery track
- preference / value track
- rupture / loss / repair track
- governance / norm track

### Design implication

A single episode should not directly overwrite identity. It may only contribute evidence to one or more tracks.

This implies a separate aggregation / governance layer above episode retention.

---

## 10. Pattern 7 — Experience may influence continuity, but not every experience may reposition identity

### Structural idea

Events affect the person, but not every event has the right to rebuild the person’s center.

### LS equivalent

LS should distinguish:

- **retained experience**
- **identity-moving continuity evidence**

### Core LS principle

> Experience may influence continuity, but only governed continuity may reposition the identity center.

### Practical meaning

A VerifiedEpisode may:

- be retained,
- become context,
- become a lesson candidate,
- become supporting / failure / contradicting evidence.

A VerifiedEpisode may **not** by itself:

- update stable identity,
- elevate its own authority,
- become a durable norm,
- become proof of character or competence by retention alone.

---

## 11. Proposed LS control flow

```text
Orientation result
    ↓
Expected transition candidate
    ↓
Authorized action execution
    ↓
Outcome Verification Center (OVC)
    ↓
VerifiedEpisode candidate
    ↓
Retention / redaction / replay / supersession checks
    ↓
Experience candidate
    ↓
Aggregation / continuity review
    ↓
Identity proposal (optional)
    ↓
Governed continuity decision
    ↓
Stable identity update (optional)
```

### Key boundaries

```text
VerifiedEpisode != identity update
```

```text
retained experience != self-authorizing memory
```

---

## 12. Schema implications for LS

### 12.1 VerifiedEpisode should explicitly carry

- `expected_transition_ref` and/or `patoc_result_ref`
- `ovc_result_ref`
- `verification_result_digest`
- `observer_set_digest`
- `observer_independence_basis`
- `episode_outcome_class`
- `evidence_role`
- `continuity_level`
- `eligible_influence`

### 12.2 OVC should reason in evidence channels

Not only an evidence list, but:

- channel kind
- dependency
- independence basis
- required channels per action class

### 12.3 ContinuityCoordinator should remain above episode retention

Identity updates should only happen after:

- aggregation
- continuity review
- governance decision

not at the episode layer.

---

## 13. Non-goals

This document does not claim:

- that Bronnikov’s physical / medical / metaphysical claims are true;
- that LS should adopt any spiritual vocabulary;
- that Bronnikov diagrams are implementation specifications.

The value of the mapping is **architectural structure only**.

---

## 14. Summary

Bronnikov materials contain structural patterns that can be reinterpreted for LS without importing unverifiable claims.

The most useful patterns are:

1. orientation before action,
2. multi-layer event representation,
3. multiple evidence channels,
4. individual / relational / system continuity levels,
5. time-structured episodes,
6. identity as a lattice of tracks,
7. a strict boundary between retained experience and identity repositioning.

The LS restatement of the core principle is:

> **Experience may influence continuity, but only governed continuity may reposition the identity center.**
