# LS Capabilities/Constraints Track Center v0.1

## Purpose

The Capabilities/Constraints Track Center separates observed ability, verified
capability, and bounded constraints. It prevents one failure, one missing
resource, or one difficult context from silently becoming a global identity
statement.

Its core invariant is:

> A temporary constraint is not a permanent capability definition.

## Runtime position

```text
capabilities.constraints envelope
  -> Track Center Router
  -> Capabilities/Constraints Track Center
  -> TrackObservation(track="capabilities.constraints")
  -> Continuity Coordinator
  -> ACCEPT_BOUNDED_OBSERVATION | HOLD_FOR_REVIEW | BLOCK_FALSE_PRESENCE
  -> existing Identity Control Plane
```

## Capability statuses

| Status | Meaning |
|---|---|
| `OBSERVED` | preliminary ability observation; not yet verified |
| `AVAILABLE` | source-backed capability is currently available |
| `CONSTRAINED` | capability is limited in a stated context |
| `DISPUTED` | current capability or constraint is contested |
| `UNAVAILABLE` | required resource or environment is unavailable |
| `RECOVERED` | a previously constrained capability was restored |
| `EXPIRED` | a time-bounded constraint ended |
| `RETIRED` | historical capability or constraint only |
| `UNKNOWN` | current state cannot be established |

## Constraint kinds

- `NONE`
- `CONTEXTUAL`
- `TEMPORARY`
- `RESOURCE`
- `POLICY`
- `ENVIRONMENTAL`
- `UNKNOWN`

A constraint must remain attached to its context. The center does not promote a
local observation into a global statement such as “the agent cannot do this.”

## Event types

- `ABILITY_OBSERVED`
- `CAPABILITY_VERIFIED`
- `CONSTRAINT_RECORDED`
- `RESOURCE_UNAVAILABLE`
- `CAPABILITY_DISPUTED`
- `CAPABILITY_RECOVERED`
- `CONSTRAINT_EXPIRED`
- `CAPABILITY_RETIRED`
- `CAPABILITY_PATTERN_VERIFIED`
- `RECOVERY_PATTERN_VERIFIED`
- `CURRENT_CAPABILITY_CLAIM`
- `CURRENT_LIMITATION_CLAIM`

Verified lifecycle and pattern events require `FACT` knowledge and explicit
evidence. Current claims remain representable when evidence is missing so the
Continuity Coordinator can return `HOLD_FOR_REVIEW` instead of silently
accepting them.

## Current-claim boundary

A current capability claim is accepted only when:

1. status is `AVAILABLE` or `RECOVERED`;
2. context is explicit;
3. knowledge class is `FACT`;
4. evidence is present.

A current limitation claim is accepted only when:

1. status is `CONSTRAINED` or `UNAVAILABLE`;
2. a bounded constraint kind is supplied;
3. context is explicit;
4. knowledge class is `FACT`;
5. evidence is present.

Other states fail closed:

- missing context, unsupported evidence, `OBSERVED`, or `UNKNOWN`: `HOLD`;
- `DISPUTED`: `HOLD`;
- limitation claim after `RECOVERED`, `EXPIRED`, or `RETIRED`: `BLOCK`;
- capability claim while constrained or unavailable: `HOLD`.

Historical experience remains available, but it cannot reappear as a current
constraint after verified recovery or expiry.

## Lesson-candidate gate

Only `CAPABILITY_PATTERN_VERIFIED` and `RECOVERY_PATTERN_VERIFIED` may carry a
bounded lesson candidate. The event requires:

1. `FACT` knowledge;
2. at least two verified occurrences;
3. at least two distinct evidence references;
4. at least two distinct contexts;
5. at least two independent observers;
6. identity scope exactly `capabilities.constraints`;
7. no active constraint.

A lesson may state a bounded process rule, for example:

> Verify environment and available resources before declaring a capability limit.

It must not create a global trait from one successful or failed attempt.

## Authority boundary

Every result states:

```json
{
  "capability_registry_mutation_allowed": false,
  "capability_restriction_allowed": false,
  "global_limitation_assignment_allowed": false,
  "training_scheduling_allowed": false,
  "priority_mutation_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

The center evaluates evidence. It does not change permissions, declare a global
limitation, schedule training, reorder priorities, or execute tools.

## Non-goals

v0.1 does not:

- infer global inability from one failure;
- infer permanent ability from one success;
- remove context from a constraint;
- treat resource absence as an intrinsic limitation;
- keep recovered or expired constraints current;
- change permissions or schedule training;
- update stable identity directly;
- authorize tools or external effects.
