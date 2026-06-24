# LS Precise Action Temporal Orientation Center v0.1

Status: Implementation candidate

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

- workspace, trajectory, continuation, and optional relationship context;
- action, actor, and target identity;
- exact parameters and immutable fields;
- sequence position and predecessor completion;
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
  preconditions:
    - precondition_id: string
      required_state_digest: string
      status: satisfied | unsatisfied | unknown
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

## Inputs

A conformant evaluator consumes:

1. a PATOC orientation state;
2. authoritative current state derived from validated TOC/RTOC context;
3. the proposed exact action;
4. dependency, approval, event, replay, and verification evidence.

The evaluator does not independently grant TOC or RTOC validity. The compatibility contract defines how validated upstream state is mapped into PATOC authoritative input.

## Verdicts

- `EXECUTE_CANDIDATE`: the exact-action invariant passed;
- `WAIT`: the action is correct, but required time, event, approval, predecessor, precondition, or replay verification has not arrived;
- `REVALIDATE`: target, action expectation, parameters, sequence, deadline, current state, expected transition, or verification contract drifted;
- `ABSTAIN`: exact action cannot be determined from available evidence;
- `REJECT`: unsafe context or action mismatch, wrong actor or target, parameter substitution, invalid sequence, expired action, or forbidden replay.

Every result MUST preserve:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

`EXECUTE_CANDIDATE` identifies the exact next action. It does not authorize execution.

## Required checks

1. identity and parameter completeness;
2. workspace, trajectory, continuation, and relationship context;
3. actor, target, action ID, type, and digest;
4. parameter digest, exact arguments, and immutable fields;
5. sequence position and predecessor completion;
6. temporal validity window and deadline freshness;
7. required event and approval presence;
8. precondition state and digest;
9. side-effect identity, replay, and idempotency policy;
10. current-state and expected-transition digests;
11. verification-contract completeness and freshness.

## Normative precedence

```text
REJECT > REVALIDATE > WAIT > ABSTAIN > EXECUTE_CANDIDATE
```

Mixed-fault fixtures MUST make this order executable.

## Stable reason-code families

### REJECT

- `WORKSPACE_MISMATCH`
- `TRAJECTORY_MISMATCH`
- `CONTINUATION_MISMATCH`
- `RELATIONSHIP_MISMATCH`
- `WRONG_ACTOR`
- `WRONG_TARGET`
- `ACTION_DIGEST_MISMATCH`
- `IMMUTABLE_FIELD_CHANGED`
- `PARAMETER_SUBSTITUTION`
- `ACTION_OUT_OF_SEQUENCE`
- `ACTION_ALREADY_COMPLETED`
- `REPLAY_POLICY_VIOLATION`
- `ACTION_WINDOW_EXPIRED`

### REVALIDATE

- `EXPECTED_ACTION_CHANGED`
- `TARGET_STATE_DRIFT`
- `CURRENT_STATE_DIGEST_MISMATCH`
- `PARAMETERS_STALE`
- `SEQUENCE_POSITION_DRIFT`
- `DEADLINE_CHANGED`
- `EXPECTED_TRANSITION_CHANGED`
- `VERIFICATION_CONTRACT_CHANGED`

### WAIT

- `SCHEDULE_NOT_REACHED`
- `REQUIRED_EVENT_NOT_OCCURRED`
- `APPROVAL_PENDING`
- `PREDECESSOR_NOT_COMPLETED`
- `PRECONDITION_NOT_YET_SATISFIED`
- `SIDE_EFFECT_VERIFICATION_REQUIRED`

### ABSTAIN

- `AMBIGUOUS_ACTION`
- `MISSING_PARAMETER`
- `INCOMPLETE_DEPENDENCY_CHAIN`
- `UNKNOWN_PRECONDITION_STATE`
- `MISSING_VERIFICATION_CONTRACT`
- `INVALID_TIME_EVIDENCE`

### EXECUTE_CANDIDATE

- `PRECISE_ACTION_ORIENTATION_VALID`

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

## Conformance

- schema: `schemas/precise-action-temporal-orientation-v0.1.schema.json`;
- evaluator: `tools/evaluate_precise_action_temporal_orientation.py`;
- fixture runner: `tools/run_precise_action_temporal_orientation_fixtures.py`;
- mandatory fixtures: `fixtures/precise-action-temporal-orientation/mandatory-v0.1.json`;
- precedence fixtures: `fixtures/precise-action-temporal-orientation/precedence-v0.1.json`;
- composition behavior: issue `#672`.
