# LS Relationship/Loss Track Center v0.1

## Purpose

The Relationship/Loss Track Center is the first concrete LS track center wired
to the Continuity Coordinator.

It converts explicit relationship events into normalized `TrackObservation`
records and delegates the final epistemic decision to the merged Continuity
Coordinator.

The center preserves one central boundary:

> A relationship may continue to influence an agent after interaction ends,
> while memory and symbolic meaning must never be promoted into fabricated
> current presence or intention.

## Runtime position

```text
relationship/loss event
  -> Relationship/Loss Track Center
  -> TrackObservation(track="relationships.loss")
  -> Continuity Coordinator
  -> ACCEPT_BOUNDED_OBSERVATION | HOLD_FOR_REVIEW | BLOCK_FALSE_PRESENCE
  -> optional bounded LessonCandidate
  -> existing Verified Episode / Identity Control Plane
```

## Event types

| Event | Required lifecycle semantics |
|---|---|
| `INTERACTION_RECORDED` | entity is `ACTIVE`; source-backed `FACT` |
| `RELATIONSHIP_CLOSED` | entity is `CLOSED` or `DELETED`; source-backed `FACT` |
| `LOSS_CONFIRMED` | entity is `DECEASED`; source-backed `FACT` |
| `REMEMBERED_INFLUENCE` | no current-presence or current-intention claim |
| `CURRENT_PRESENCE_CLAIM` | explicit current-presence claim for continuity review |
| `CURRENT_INTENTION_CLAIM` | explicit current-intention claim for continuity review |

Lifecycle events fail closed when status, epistemic class, or evidence does not
match the event type.

## Identity-learning boundary

Only two event types may carry a bounded identity lesson candidate:

- `INTERACTION_RECORDED`;
- `REMEMBERED_INFLUENCE`.

Current-presence and current-intention claims cannot propose an identity lesson.
Confirmed death or closure also cannot directly create one.

A candidate that survives the Continuity Coordinator is still only a
`LessonCandidate`. It must pass through:

```text
Verified Episode
  -> at least three consistent episodes
  -> IdentityUpdateProposal
  -> independent approval
  -> durable patch commit
  -> activation / rollback
```

## Relational Self integration

LS already contains a legacy/experimental `RelationalSelf` graph snapshot.
Relationship/Loss Track Center v0.1 deliberately does not mutate it.

Every result states:

```json
{
  "relational_self_mutation_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

A future adapter may update Relational Self only after a separately governed
identity application. This prevents an emotional observation, memory, or single
relationship event from silently changing the agent's long-term self-model.

## Deterministic result

The result ID binds:

- canonical event digest;
- normalized observation digest;
- Continuity Coordinator assessment ID;
- track-center policy version.

The output bundle includes the original event, normalized observation, and full
continuity assessment for inspection and replay.

## Example outcomes

### Remembered influence after confirmed loss

```text
REMEMBERED_INFLUENCE + DECEASED + MEMORY
  -> ACCEPT_BOUNDED_OBSERVATION
  -> historical influence preserved
  -> optional bounded LessonCandidate
  -> no direct identity mutation
```

### Fabricated current intention after closure

```text
CURRENT_INTENTION_CLAIM + CLOSED + INFERENCE
  -> BLOCK_FALSE_PRESENCE
  -> historical influence preserved
  -> no lesson
  -> no action authority
```

### Unknown current-presence claim

```text
CURRENT_PRESENCE_CLAIM + UNKNOWN + INFERENCE
  -> HOLD_FOR_REVIEW
  -> no lesson
  -> no mutation
```

## Non-claims

v0.1 does not diagnose grief, delusion, psychosis, attachment style, or any
medical condition.

v0.1 does not decide metaphysical questions about consciousness after death.

v0.1 does not infer event types from free-form text. Upstream callers must set
the event type, entity status, epistemic class, and evidence references
explicitly.
