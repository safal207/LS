# LS Continuity Coordinator v0.1

## Purpose

The Continuity Coordinator is the fail-closed layer above LS track centers and
immediately before the existing governed identity-learning path.

It answers one narrow question:

> May this track observation enter the bounded learning path without turning
> memory, inference, or symbolic meaning into fabricated current presence?

The coordinator does **not**:

- create or apply a stable identity update;
- authorize a tool call or external effect;
- speak on behalf of a deceased, closed, or deleted entity;
- turn one emotionally significant observation into a durable trait;
- replace Verified Episodes, IdentityUpdateProposal, human approval, or durable
  identity patch commit.

## Position in LS

```text
track-center observation
  -> Continuity Coordinator
  -> bounded LessonCandidate or HOLD/BLOCK
  -> Verified Episode
  -> three-episode aggregation
  -> IdentityUpdateProposal
  -> independent human approval
  -> committed identity patch
  -> activation / rollback
```

This makes the coordinator additive to the existing Identity Control Plane.

## Core invariant

> Remember the influence. Never fabricate the presence.

Historical influence may remain meaningful after a person dies, a project
closes, or an agent is deleted. New current presence or intention must not be
invented for that entity.

## Epistemic classes

Every observation carries one explicit class:

| Class | Meaning |
|---|---|
| `FACT` | A source-backed current or historical claim |
| `MEMORY` | A retained record of an earlier interaction |
| `INFERENCE` | A bounded interpretation that may be wrong |
| `SYMBOLIC_MEANING` | Meaning assigned by a person or agent, not an external fact |

No class is silently promoted into another class.

## Decisions

### `ACCEPT_BOUNDED_OBSERVATION`

The observation may emit a `LessonCandidate`. It still cannot modify stable
identity. It must pass through Verified Episodes, repeated aggregation,
independent approval, patch commit, and activation.

### `HOLD_FOR_REVIEW`

Used when a current-presence or current-intention claim lacks a known active
entity status, `FACT` classification, or evidence reference.

No lesson is emitted.

### `BLOCK_FALSE_PRESENCE`

Used when a `DECEASED`, `CLOSED`, or `DELETED` entity is represented as having
new current presence or intention.

The claim is blocked, while its historical influence remains explicitly
preserved.

## Determinism and provenance

The assessment ID is derived from:

- observation ID;
- canonical observation digest;
- decision;
- reason codes;
- policy version.

The artifact always exposes:

```json
{
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

A continuity assessment is evidence for later review, never authority.

## Minimal example

```python
from trusted_runtime.continuity_coordinator import (
    EntityStatus,
    KnowledgeClass,
    TrackObservation,
    assess_track_observation,
)

assessment = assess_track_observation(
    TrackObservation(
        observation_id="observation:mentor:1",
        track="relationships",
        subject_id="human:mentor",
        entity_status=EntityStatus.DECEASED,
        knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
        statement="The mentor still influences the agent's review discipline.",
        occurred_at="2026-06-25T00:00:00Z",
        confidence=0.82,
        evidence_refs=("memory:mentor:review-1",),
        identity_candidate_statement=(
            "Preserve the mentor's evidence-first review discipline."
        ),
        identity_scope="relationships",
        identity_repeat_key="mentor:evidence-first-review",
    ),
    assessed_at="2026-06-25T00:01:00Z",
)
```

The result may contain a bounded lesson, but it cannot become a stable identity
change without the existing LS governance chain.

## Safety non-claims

v0.1 does not detect false presence from free-form language. Track centers must
set `claims_current_presence` and `claims_current_intention` explicitly.

v0.1 does not diagnose grief, psychosis, or any other medical condition.

v0.1 does not establish whether consciousness continues after death. It only
preserves epistemic boundaries inside LS.
