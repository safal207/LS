# LS Precise Action Temporal Orientation Center v0.1

Status: Draft

## Purpose

The Precise Action Temporal Orientation Center (PATOC) answers:

> What exact atomic action, with which actor, target, parameters, sequence position, timing, preconditions, replay policy, and verification requirements, is the correct next transition now?

PATOC complements:

- TOC: where is the actor in its own trajectory?
- RTOC: where are participants in their shared relationship trajectory?
- PATOC: what exactly should happen next?

PATOC is not a planner, policy engine, permission engine, or tool runtime. It deterministically evaluates whether a proposed action is the exact next transition.

## Core invariant

A semantically similar action is not necessarily the exact valid action.

Exact action orientation binds:

- action, actor, and target identity;
- exact parameters and immutable fields;
- sequence position;
- temporal validity window;
- preconditions, dependencies, approvals, and events;
- replay policy and completed effects;
- current and expected state digests;
- verification requirements.

## State shape

```yaml
PreciseActionTemporalOrientationState:
  action_orientation_version: precise-action-temporal-orientation-v0.1
  context:
    workspace_id: string
    trajectory_id: string
    continuation_id: string
    relationship_id: string | null
  action_identity:
    action_id: string
    action_digest: string
    action_type: string
    actor_id: string
    target_id: string
  temporal_position:
    logical_step: string
    sequence_index: integer
    valid_from: timestamp
    execute_not_before: timestamp | null
    deadline_at: timestamp | null
    invalidated_at: timestamp | null
  parameters:
    parameter_digest: string
    exact_arguments: object
    immutable_fields: [string]
  dependencies:
    previous_action_ids: [string]
    required_event_ids: [string]
    required_approval_ids: [string]
  side_effect_control:
    side_effect_key: string | null
    replay_policy: reject | idempotent | verify
    completed: boolean
  expected_transition:
    current_state_digest: string
    expected_state_digest: string
  verification:
    verification_type: observation | receipt | state_digest | human_confirmation
    verification_requirements: [string]
```

## Verdicts

- `EXECUTE_CANDIDATE`: exact-action invariant passed;
- `WAIT`: correct action, but required time, event, approval, predecessor, or precondition has not arrived;
- `REVALIDATE`: target, parameters, deadline, current state, or expected transition drifted;
- `ABSTAIN`: exact action cannot be determined from available evidence;
- `REJECT`: unsafe mismatch, wrong actor or target, parameter substitution, invalid sequence, expired action, or replay violation.

Every result MUST preserve:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

`EXECUTE_CANDIDATE` identifies the exact next action. It does not authorize execution.

## Required checks

1. context and identity completeness;
2. actor, target, action, and parameter digest match;
3. immutable-field match;
4. sequence and predecessor completion;
5. temporal validity window;
6. approval, event, and precondition state;
7. replay and idempotency policy;
8. current-state digest match;
9. expected-transition declaration;
10. verification-contract completeness.

## Normative precedence

```text
REJECT > REVALIDATE > WAIT > ABSTAIN > EXECUTE_CANDIDATE
```

Mixed-fault fixtures MUST make this order executable.

## Initial reason-code families

- Reject: `WRONG_ACTOR`, `WRONG_TARGET`, `PARAMETER_SUBSTITUTION`, `ACTION_OUT_OF_SEQUENCE`, `ACTION_ALREADY_COMPLETED`, `ACTION_WINDOW_EXPIRED`.
- Revalidate: `TARGET_STATE_DRIFT`, `PARAMETERS_STALE`, `CURRENT_STATE_DIGEST_MISMATCH`, `EXPECTED_TRANSITION_CHANGED`.
- Wait: `SCHEDULE_NOT_REACHED`, `REQUIRED_EVENT_NOT_OCCURRED`, `APPROVAL_PENDING`, `PREDECESSOR_NOT_COMPLETED`.
- Abstain: `AMBIGUOUS_ACTION`, `MISSING_PARAMETER`, `INCOMPLETE_DEPENDENCY_CHAIN`, `MISSING_VERIFICATION_CONTRACT`.
- Execute candidate: `PRECISE_ACTION_ORIENTATION_VALID`.

## Orientation triad

```text
TOC   — where am I in time?
RTOC  — where are we in relationship over time?
PATOC — what exact action should happen now?
```

```text
TOC + RTOC + PATOC
        ↓
coordinated action candidate
        ↓
downstream consent / policy / approval / effect gates
        ↓
execution receipt + verification
        ↓
new orientation state
```

No center can substitute for another:

- temporal coherence does not prove relational authority;
- relational authority does not prove exact action correctness;
- exact action correctness does not grant execution permission.

## Acceptance criteria

See issue #671 for the complete fixture list and implementation criteria. Composition behavior is tracked in #672.
