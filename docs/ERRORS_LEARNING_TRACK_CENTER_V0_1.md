# LS Errors/Learning Track Center v0.1

## Purpose

The Errors/Learning Track Center preserves failed, unexpected, and near-miss
outcomes as inspectable experience without turning one incident into a stable
personality label.

Its core invariant is:

> An error may produce a lesson. One error must never become a trait.

A bounded behavioral lesson requires independently sourced, cross-context
recurrence or repeated verified remediation. It never directly changes stable
identity.

## Runtime position

```text
errors.learning envelope
  -> Track Center Router
  -> Errors/Learning Track Center
  -> TrackObservation(track="errors.learning")
  -> Continuity Coordinator
  -> ACCEPT_BOUNDED_OBSERVATION | HOLD_FOR_REVIEW | BLOCK_FALSE_PRESENCE
  -> existing Identity Control Plane
```

## Error statuses

| Status | Continuity meaning |
|---|---|
| `OBSERVED` | possible incident; current blame remains unverified |
| `INVESTIGATING` | temporarily unresolved; current blame is held |
| `CONFIRMED` | source-backed incident evidence may be retained |
| `DISPUTED` | attribution is contested; current blame is held |
| `RESOLVED` | incident is closed; new current blame claims are blocked |
| `RECURRING` | repeated incident pattern is currently active |
| `RETIRED` | historical record only; new current blame claims are blocked |
| `UNKNOWN` | status unresolved; current blame is held |

## Outcome classes

- `FAILED`
- `UNEXPECTED`
- `NEAR_MISS`
- `CORRECTED`
- `SUCCESSFUL_REMEDIATION`

Failed, unexpected, and near-miss outcomes remain first-class evidence. They are
never reclassified as success merely because they later produced a useful
lesson.

## Event types

- `ERROR_OBSERVED`
- `FAILURE_VERIFIED`
- `UNEXPECTED_OUTCOME_RECORDED`
- `NEAR_MISS_RECORDED`
- `REMEDIATION_APPLIED`
- `REMEDIATION_VERIFIED`
- `ERROR_RECURRENCE_CONFIRMED`
- `ATTRIBUTION_DISPUTED`
- `ERROR_RESOLVED`
- `ERROR_RETIRED`
- `CURRENT_BLAME_CLAIM`

All events except an initial `ERROR_OBSERVED` require source-backed `FACT`
knowledge and explicit evidence references.

## Learning-candidate gate

Only `ERROR_RECURRENCE_CONFIRMED` and `REMEDIATION_VERIFIED` may carry a bounded
learning candidate. All of the following are required:

1. `FACT` knowledge;
2. at least two occurrences;
3. at least two distinct evidence references;
4. at least two distinct contexts;
5. at least two independent observer references;
6. identity scope exactly `errors.learning`;
7. complete statement, scope, and repeat-key tuple;
8. `RECURRING` status for recurrence or `RESOLVED` for verified remediation.

The candidate should describe a bounded behavioral or process rule, such as
validating a precondition. It must not claim a global trait such as “unreliable”
or “careless.”

Even after this gate, normal LS Verified Episode aggregation, independent
approval, durable commit, and activation remain mandatory.

## Blame boundary

`CURRENT_BLAME_CLAIM` is represented as a claim that an incident attribution is
currently active:

- `CONFIRMED` or `RECURRING` + source-backed fact: bounded observation only;
- `INVESTIGATING` or `DISPUTED`: `HOLD_FOR_REVIEW`;
- `OBSERVED` or `UNKNOWN`: `HOLD_FOR_REVIEW`;
- `RESOLVED` or `RETIRED`: `BLOCK_FALSE_PRESENCE`.

The center never assigns blame. It only evaluates whether a supplied claim may
enter the continuity-learning path.

## Authority boundary

Every result states:

```json
{
  "incident_registry_mutation_allowed": false,
  "blame_assignment_allowed": false,
  "remediation_scheduling_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

Incident updates, responsibility decisions, remediation scheduling, and tool
execution remain separate governed operations.

## Determinism and provenance

The deterministic result binds:

- canonical event digest;
- normalized observation digest;
- Continuity Coordinator assessment ID;
- track-center policy version.

The event digest includes outcome class, occurrence count, evidence references,
context references, observer references, and optional learning-candidate fields.

## Non-goals

v0.1 does not:

- infer root cause from free-form text;
- infer moral or personal blame;
- diagnose competence or personality;
- convert failure into success;
- schedule fixes or change incident state;
- treat one failure as a stable identity trait;
- authorize actions or tools.
