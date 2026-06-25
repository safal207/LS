# LS Values Track Center v0.1

## Purpose

The Values Track Center separates durable value evidence from moods, transient
preferences, slogans, and one-off statements.

Its core invariant is:

> A statement is not a value.

Repeated, source-backed evidence across different contexts may create a bounded
`LessonCandidate`. It never creates an automatic stable-identity update.

## Runtime position

```text
values.evidence envelope
  -> Track Center Router
  -> Values Track Center
  -> TrackObservation(track="values.evidence")
  -> Continuity Coordinator
  -> ACCEPT_BOUNDED_OBSERVATION | HOLD_FOR_REVIEW | BLOCK_FALSE_PRESENCE
  -> existing Identity Control Plane
```

## Value statuses

| Status | Meaning |
|---|---|
| `CANDIDATE` | possible value signal; not established as current guidance |
| `ACTIVE` | source-backed current value evidence may be reviewed |
| `CONTESTED` | current guidance is disputed; current claims are held |
| `RETIRED` | historical influence may remain; current claims are blocked |
| `UNKNOWN` | status is unresolved; current claims are held |

`CONTESTED` maps to temporarily inactive continuity semantics. `RETIRED` maps to
closed continuity semantics.

## Event types

### Evidence-bearing events

- `VALUE_SIGNAL_OBSERVED`
- `VALUE_REAFFIRMED`
- `VALUE_PRACTICED`
- `VALUE_CONFLICT_RECORDED`
- `VALUE_RETIRED`
- `CURRENT_VALUE_CLAIM`

### Explicitly non-durable signals

- `TRANSIENT_PREFERENCE_OBSERVED`
- `MOOD_SIGNAL_OBSERVED`

Mood and preference events can be retained as observations but cannot propose an
identity lesson.

## Identity-candidate gate

Only `VALUE_REAFFIRMED` and `VALUE_PRACTICED` may carry an identity candidate,
and only when all of the following hold:

1. status is `ACTIVE`;
2. knowledge class is `FACT`;
3. `repeat_count >= 2`;
4. at least two distinct evidence references exist;
5. at least two distinct context references exist;
6. identity statement, scope, and repeat key are all present.

This means repetition in one conversation or one environment is not enough.

Even after this gate, the result is only a bounded `LessonCandidate`. The normal
LS Verified Episode, aggregation, independent approval, durable commit, and
activation chain remains mandatory.

## Current-value claims

A current-value claim is treated as current intention evidence:

- `ACTIVE` + source-backed `FACT`: bounded observation;
- `CANDIDATE` or `UNKNOWN`: `HOLD_FOR_REVIEW`;
- `CONTESTED`: `HOLD_FOR_REVIEW` with temporarily inactive reason;
- `RETIRED`: `BLOCK_FALSE_PRESENCE` for false current intention.

A retired value may remain historically meaningful, but it cannot silently
continue steering priorities.

## Authority boundary

Every result states:

```json
{
  "value_registry_mutation_allowed": false,
  "priority_mutation_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

The center records evidence. It does not set values, reorder priorities, make
decisions, or execute tools.

## Determinism and provenance

The value result ID binds:

- canonical value-event digest;
- normalized observation digest;
- Continuity Coordinator assessment ID;
- Values Track Center policy version.

The event digest includes repeat count, evidence references, context references,
status, knowledge class, and optional identity-candidate fields.

## Non-goals

v0.1 does not:

- infer values from arbitrary free-form text;
- treat emotional intensity as durability;
- equate preference with principle;
- resolve moral conflicts automatically;
- rank values or modify priorities;
- diagnose personality;
- let one event become a stable trait.
