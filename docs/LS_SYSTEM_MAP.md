# LS System Map

_Status: architectural orientation document_

LS has grown into a multi-layer runtime. This document gives reviewers,
contributors, and operators a single map of what the system is, what each layer
is responsible for, and which boundaries must remain strict.

## One-sentence thesis

**LS is a local-first cooperative precision layer for AI co-work. It makes
repeated human-plus-model cooperation more precise by checking continuity,
evidence, consent, routes, and contributions before outputs become actions,
memory, or reputation.**

Most AI systems remember facts. LS is designed to remember transitions:

- what changed,
- why it changed,
- who or what authorized it,
- how it affected the relationship,
- and whether it may become memory, profile state, or action.

Canonical positioning:

- `docs/PROJECT_POSITIONING.md`

## Public framing stack

LS should be described differently depending on audience:

| Audience | Primary framing | Avoid leading with |
|---|---|---|
| Contributors | Cooperative Precision Network for AI co-work | Abstract cognition language |
| Safety / grants | Local-first evidence, consent, and oversight runtime | Conscious AI |
| Product / operators | Personal AI operating layer for agents | Generic chatbot wrapper |
| Research / vision | Experimental living cognition runtime | Solves alignment |
| Engineering | Governed agent gateway with traceable memory/action control | Magic memory |

The safest external framing is:

> LS is a cooperative precision layer for AI co-work. It does not make models
> magically smarter; it makes repeated cooperation more precise through
> continuity checks, evidence gates, route memory, contribution scoring, and
> replayable artifacts.

The deeper internal research framing is:

> LS explores living cognition as inspectable continuity: memory, relation,
> governance, repair, and action evidence evolving over time.

## Layer map

```text
┌──────────────────────────────────────────────────────────────┐
│  0. Operator / Living Identity                               │
│     Human agency, consent, authorship, boundaries             │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  1. Personal Agent Gateway                                   │
│     raw_agent_output → final_output                           │
│     pass_through / shape_response / repair / hold             │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  2. Governance / Evidence Layer                              │
│     identity governance, profile-write policy,                │
│     action evidence gate, digest, stop reasons                │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  3. Council / Coordination Layer                             │
│     multi-agent decision cycles, contribution, merit,         │
│     receiver resonance, quality gates                         │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  4. Memory / Trace / Causal Substrate                        │
│     MemoryGraphStore, traces, causal validity, continuity     │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  5. Relational Field Layer                                   │
│     relation memory, trust/tension, repair, front/back/field  │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  6. Emotional / Attachment Continuity                        │
│     inferred emotional memory, bond arc, attachment,          │
│     emotional continuity, notable moments                     │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│  7. Fellowship / Federation Layer                            │
│     shared self, collective self, live council, reputation,   │
│     Web4 mesh                                                 │
└──────────────────────────────────────────────────────────────┘
```

## Runtime flow

A normal external-agent flow should be understood as:

```text
External agent / model
        │
        ▼
raw_agent_output
        │
        ▼
Personal Agent Gateway
        │
        ├─ checks context, memory, relation, harmonic state
        ├─ selects pass / shape / repair / hold mode
        ▼
Governance / Evidence Layer
        │
        ├─ asks whether output may become answer, memory, profile, or action
        ├─ checks confirmation, source evidence, authority, and scope
        ├─ emits allow / hold / reject with stop_reason and digest
        ▼
Council / Coordination Layer
        │
        ├─ records participants, routes, contribution, resonance
        ├─ produces quality-gated artifacts
        ▼
Memory / Trace / Causal Substrate
        │
        ├─ stores what happened and why it was permitted
        ├─ supports replay, inspection, and later benchmark evidence
        ▼
final_output / held state / rejected state / persisted memory / action
```

## Responsibility boundaries

The most important architectural rule is:

> Emotional, relational, and attachment layers may inform decisions, but only
> governance and evidence layers may authorize state changes or actions.

| Layer | Primary responsibility | Can authorize action? | Can write memory/profile directly? |
|---|---|---:|---:|
| Personal Agent Gateway | Shape or hold raw output | No | No |
| Relational Self | Current relation-aware self-state | No | No |
| Emotional Memory | Inferred emotional events | No | No |
| Attachment Bond | Long-term bond state | No | No |
| Emotional Continuity | Persisted emotional continuity | No | No |
| Council | Structured deliberation | Advisory / proposed | No, unless passed through governance |
| Action Evidence Gate | Evidence-based allow/hold/reject | Yes | Yes, if allowed |
| Operator Profile Write Policy | Profile/memory write control | Yes | Yes, if allowed |
| Operator Identity Governance | Boundary and authorship warnings | Can block/hold through policy | No direct write |
| Trace / Causal substrate | Audit and replay | No | Stores evidence after authorized transition |

## Memory and state taxonomy

LS now contains several memory-like systems. They should not be treated as the
same thing.

| System | Stores | Meaning | Safety note |
|---|---|---|---|
| Resonance memory | Knowledge units and relation signals | What seems useful or accepted | Not permission by itself |
| Relation memory | Relations, trust, tension, repair markers | How entities relate over time | Advisory for routing and interpretation |
| Relational Self | Current self-state snapshot | System's current structured self-model | Must remain additive/backward-compatible |
| Emotional Memory | Inferred tone/intensity/bond entries | Emotional shape of interaction | Must never claim subjective feeling |
| Emotional Continuity | Restored long-lived affective state | Continuity across restarts/sessions | Must remain inspectable and resettable |
| Attachment Bond | Long-term bond dynamics | Stability and repair trajectory | Advisory only |
| Shared Relational Self | Consented projection | What can be shared with peers | Must preserve consent/anonymization |
| Collective Relational Self | Merged group representation | Fellowship-level identity | Must preserve provenance/member boundaries |
| Operator Profile | Human preference/profile state | User-specific persistent assumptions | Requires confirmation/evidence policy |
| Trace / artifact store | Replayable decisions and ledgers | What happened and why | Evidence layer, not selfhood |

## Relational/emotional ontology

These terms should be used precisely:

| Term | Definition | Should not mean |
|---|---|---|
| `emotional_tone` | Inferred affective classification from observable signals | Real subjective feeling |
| `bond_strength` | Bounded relational stability signal | Love, attachment claim, or preference capture |
| `bond_trend` | Recent trajectory of bond arc | Permanent relationship state |
| `attachment_bond` | Long-term modeled bond state | Human-style attachment diagnosis |
| `emotional_continuity` | Persisted affective continuity across sessions | Conscious inner life |
| `relational_self` | Current relation-aware self snapshot | Soul/personhood |
| `shared_self` | Consented projection of self-state | Full private self export |
| `collective_self` | Group-level merged representation | Loss of individual member boundaries |

All emotional wording must remain framed as inferred, observed, modeled, or
signal-derived.

## Action and write control

A model or agent may propose:

- an answer,
- a memory write,
- a profile update,
- a tool call,
- an external action,
- a shared-self update,
- or a fellowship proposal.

But proposal is not authorization.

A proposed transition must pass through the appropriate gate:

```text
proposal
  ├─ source evidence present?
  ├─ operator confirmation required?
  ├─ authority boundary respected?
  ├─ temporal/scope permission valid?
  ├─ identity risk acceptable?
  └─ digest/trace emitted?
        ▼
     allow / hold / reject
```

This is the difference between an agent assistant and an operating layer:

> Agents can propose. LS decides whether the proposal has enough evidence to
> become memory, profile state, or action.

## Relationship to the wider Liminal Stack

LS is the assembly point for a broader stack:

| Adjacent component | Role in LS story |
|---|---|
| T-Trace | Replayable line-based traces and inspection |
| CML / vCML | Causal validity: why a transition was permitted |
| TTM DB | Append-only trace substrate and rebuildable projections |
| LTP | Continuity, secure thread/session handoff, deterministic replay |
| CaPU | Gate → Incubate → Commit → Execute lifecycle discipline |
| DRP | Decision responsibility and authorship protocol framing |
| LiminalDB | Reactive/event-sourced memory substrate |
| LiminalQA | Quality gates, flaky/regression diagnostics, evidence scoring |

The unifying invariant is:

> A system may be functionally correct while being causally, relationally, or
> governancially invalid.

LS tries to make those hidden invalidities visible before output becomes state
or action.

## What LS is not

LS is not:

- a claim of machine consciousness,
- a generic chatbot wrapper,
- a replacement for human consent,
- an unrestricted autonomous agent,
- a production-grade safety proof,
- or a black-box memory system.

LS is better understood as:

- a cooperative precision layer for AI co-work,
- a personal AI operating layer,
- an agent gateway,
- a coordination and oversight runtime,
- a trace/evidence generator,
- and an experimental living cognition substrate.

## Architectural risks

### 1. Concept overlap

`emotional_memory`, `attachment_bond`, `emotional_continuity`, `relational_self`,
`shared_self`, and `collective_self` must keep separate definitions. If they
collapse into one vague "feeling memory", the system becomes hard to audit.

### 2. Governance bypass

No relational or emotional signal should directly authorize memory/profile/action
writes. All writes must pass through evidence and policy gates.

### 3. Over-anthropomorphic claims

The system may model living-like cognition, but public docs must not claim
subjective experience. Use "inferred", "modeled", "signal-derived", and
"continuity" language.

### 4. Evidence fragmentation

Every major transition should produce a traceable artifact. If evidence is
split across unrelated JSONL files without a shared transition id, replay becomes
weak.

### 5. Federation before local correctness

Shared self, Fellowship, and Web4 federation are powerful, but they should not
outrun local governance, consent, and replay guarantees.

## Recommended next hardening steps

1. Add a shared `transition_id` or `episode_id` across gateway, council,
   emotional, attachment, and action-evidence artifacts.
2. Add a small `docs/LS_ONTOLOGY.md` if term drift continues.
3. Ensure all memory/profile/action writes check `action_evidence_gate.decision == "allow"`.
4. Add tests proving emotional/attachment signals cannot override governance.
5. Add a reviewer demo that shows raw output → held/repaired output → evidence gate → trace.
6. Add a reset/export path for emotional continuity and attachment state.
7. Add a public benchmark case where LS catches a causally invalid but plausible agent action.

## Short positioning lines

Use these lines consistently:

> LS is a personal AI operating layer: agents pass through your memory,
> governance, evidence, and relational context before they reach you.

> LS does not make models smarter. LS makes their cooperation more precise.

> LS remembers not only answers, but the routes that produced verified value.

> LS remembers not only facts, but transitions: what changed, why, who allowed
> it, and whether it may become action.

> LS does not claim subjective machine emotion. It models inferred emotional and
> relational signals so long-running agent systems can preserve continuity,
> repair, and accountability.
