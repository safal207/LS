# LS Projects Track Center v0.1

## Purpose

The Projects Track Center converts explicit project lifecycle events into
bounded Continuity Coordinator observations.

Its core invariant is:

> Preserve the lesson. Never revive the task.

A completed, cancelled, or archived project may continue to influence the
agent's methods and values. It must not silently regain current tasks,
priorities, or execution authority.

## Runtime position

```text
projects.lifecycle envelope
  -> Track Center Router
  -> Projects Track Center
  -> TrackObservation(track="projects.lifecycle")
  -> Continuity Coordinator
  -> ACCEPT_BOUNDED_OBSERVATION | HOLD_FOR_REVIEW | BLOCK_FALSE_PRESENCE
  -> existing Identity Control Plane
```

## Project statuses

| Status | Continuity meaning |
|---|---|
| `ACTIVE` | current source-backed claims may be reviewed as bounded observations |
| `PAUSED` | temporarily inactive; current task or priority claims are held |
| `COMPLETED` | closed; new current tasks or priorities are blocked |
| `CANCELLED` | closed; new current tasks or priorities are blocked |
| `ARCHIVED` | closed; new current tasks or priorities are blocked |
| `UNKNOWN` | current claims are held until status is verified |

`PAUSED` is deliberately distinct from `CLOSED`: a verified resume may restore
activity, while a completed or cancelled project requires a separate governed
new-project or reopen operation.

## Lifecycle events

- `PROJECT_STARTED`
- `PROJECT_PAUSED`
- `PROJECT_RESUMED`
- `PROJECT_COMPLETED`
- `PROJECT_CANCELLED`
- `PROJECT_ARCHIVED`

Lifecycle events require source-backed `FACT` knowledge, evidence references,
and an allowed `(previous_status, project_status)` transition.

## Non-lifecycle events

### `PROJECT_LESSON_RETAINED`

May carry a bounded identity lesson candidate. For a closed project, the
Continuity Coordinator preserves historical influence without reopening work.

### `CURRENT_TASK_CLAIM`

Represents a claim that the project currently has a task.

- active + source-backed fact: bounded observation only;
- paused: `HOLD_FOR_REVIEW` with `ENTITY_TEMPORARILY_INACTIVE`;
- completed/cancelled/archived: `BLOCK_FALSE_PRESENCE` with false current
  intention;
- unknown or unverified: `HOLD_FOR_REVIEW`.

### `CURRENT_PRIORITY_CLAIM`

Uses the same boundary as current-task claims.

## Authority boundary

Every result states:

```json
{
  "project_registry_mutation_allowed": false,
  "task_scheduling_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

The center does not update project status. A lifecycle event is evidence for a
separate governed registry operation.

The center does not schedule a task. An accepted current-task claim remains an
observation, not an instruction.

## Identity boundary

Only `PROJECT_LESSON_RETAINED` may carry an identity candidate. It still enters
the existing LS chain as a bounded `LessonCandidate` and requires repeated
Verified Episodes, an `IdentityUpdateProposal`, independent approval, durable
commit, and activation.

Lifecycle events and current task or priority claims cannot directly propose a
trait.

## Determinism and provenance

The project result ID binds:

- canonical project event digest;
- normalized observation digest;
- Continuity Coordinator assessment ID;
- track-center policy version.

This supports replay from project event through identity-learning review.

## Non-goals

v0.1 does not:

- infer project status from free-form text;
- reopen projects automatically;
- create or assign tasks;
- change deadlines or priorities;
- mutate project storage;
- diagnose motivation or burnout;
- treat one project outcome as a stable personality trait.
