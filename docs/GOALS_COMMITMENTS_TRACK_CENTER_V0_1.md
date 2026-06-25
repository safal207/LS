# LS Goals/Commitments Track Center v0.1

## Purpose

The Goals/Commitments Track Center separates wishes, intentions, plans,
commitments, and obligations. It prevents a casual statement from silently
becoming a duty and prevents a completed, cancelled, expired, or retired goal
from remaining as permanent debt.

Its core invariant is:

> A wish is not a commitment. A closed goal is not a current obligation.

## Runtime position

```text
goals.commitments envelope
  -> Track Center Router
  -> Goals/Commitments Track Center
  -> TrackObservation(track="goals.commitments")
  -> Continuity Coordinator
  -> ACCEPT_BOUNDED_OBSERVATION | HOLD_FOR_REVIEW | BLOCK_FALSE_PRESENCE
  -> existing Identity Control Plane
```

## Commitment levels

| Level | Meaning |
|---|---|
| `WISH` | desired possibility; no duty |
| `INTENTION` | stated direction; no verified commitment |
| `PLAN` | proposed method or sequence; no duty by itself |
| `COMMITMENT` | explicit source-backed promise or undertaking |
| `OBLIGATION` | explicitly accepted duty with source-backed evidence |

Only `COMMITMENT` and `OBLIGATION` may appear in a
`CURRENT_DUTY_CLAIM`.

## Goal statuses

| Status | Continuity meaning |
|---|---|
| `PROPOSED` | not yet an active duty |
| `ACTIVE` | current commitment evidence may be evaluated |
| `PAUSED` | current duty claims are held pending verified reactivation |
| `DISPUTED` | obligation is contested; current duty claims are held |
| `COMPLETED` | historical outcome retained; new current duty claims blocked |
| `CANCELLED` | released goal; new current duty claims blocked |
| `EXPIRED` | time-bounded duty ended; new current duty claims blocked |
| `RETIRED` | historical influence only; new current duty claims blocked |
| `UNKNOWN` | status unresolved; current duty claims are held |

## Event types

- `WISH_OBSERVED`
- `INTENTION_STATED`
- `PLAN_RECORDED`
- `COMMITMENT_DECLARED`
- `COMMITMENT_REAFFIRMED`
- `OBLIGATION_ACCEPTED`
- `FOLLOW_THROUGH_VERIFIED`
- `COMMITMENT_PAUSED`
- `COMMITMENT_COMPLETED`
- `COMMITMENT_CANCELLED`
- `COMMITMENT_EXPIRED`
- `COMMITMENT_RETIRED`
- `COMMITMENT_RELEASE_VERIFIED`
- `CURRENT_DUTY_CLAIM`

Source-backed commitment, obligation, lifecycle, release, and current-duty events
require `FACT` knowledge and explicit evidence references.

## Current-duty boundary

A current-duty claim is accepted only as a bounded observation when:

1. level is `COMMITMENT` or `OBLIGATION`;
2. status is `ACTIVE`;
3. knowledge class is `FACT`;
4. evidence is present.

Other states fail closed:

- `PROPOSED` or `UNKNOWN`: `HOLD_FOR_REVIEW`;
- `PAUSED` or `DISPUTED`: `HOLD_FOR_REVIEW`;
- `COMPLETED`, `CANCELLED`, `EXPIRED`, or `RETIRED`:
  `BLOCK_FALSE_PRESENCE`.

Historical meaning may remain, but the goal cannot silently regain current-duty
status.

## Lesson-candidate gate

Only `FOLLOW_THROUGH_VERIFIED` and `COMMITMENT_RELEASE_VERIFIED` may carry a
bounded lesson candidate. All of the following are required:

1. `FACT` knowledge;
2. at least two verified occurrences;
3. at least two distinct evidence references;
4. at least two distinct contexts;
5. at least two distinct commitment references;
6. level `COMMITMENT` or `OBLIGATION`;
7. identity scope exactly `goals.commitments`;
8. `COMPLETED` status for follow-through or a released status for release.

A lesson should describe a bounded process rule such as confirming scope before
accepting a deadline. It must not automatically create a global trait or moral
judgment.

## Authority boundary

Every result states:

```json
{
  "goal_registry_mutation_allowed": false,
  "obligation_assignment_allowed": false,
  "work_scheduling_allowed": false,
  "priority_mutation_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

The center records and evaluates evidence. It does not create obligations,
modify goals, schedule work, reorder priorities, or execute tools.

## Determinism and provenance

The deterministic result binds:

- canonical event digest;
- normalized observation digest;
- Continuity Coordinator assessment ID;
- track-center policy version.

The event digest includes commitment level, status, repeat count, evidence,
contexts, commitment references, and optional lesson-candidate fields.

## Non-goals

v0.1 does not:

- infer commitment from enthusiasm or repetition alone;
- treat a plan as a promise;
- assign moral guilt for cancellation;
- keep completed or cancelled goals as current debt;
- schedule tasks or alter priorities;
- create a stable personality trait from one commitment;
- authorize tools or external effects.
