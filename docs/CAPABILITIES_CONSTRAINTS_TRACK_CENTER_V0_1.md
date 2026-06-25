# LS Capabilities/Constraints Track Center v0.1

## Purpose

The Capabilities/Constraints Track Center preserves evidence about what an agent
can do, cannot currently do, or has recovered from doing without turning one
observation into permanent identity.

Core invariant:

> A temporary constraint is not a permanent incapability. A local failure must
> not silently become global inability.

## Runtime position

```text
capabilities.constraints envelope
  -> Track Center Router
  -> Capabilities/Constraints Track Center
  -> TrackObservation
  -> Continuity Coordinator
  -> bounded LessonCandidate | HOLD | BLOCK
```

The center never mutates a capability registry, denies access, assigns permanent
incapacity, schedules training, changes priorities, updates stable identity, or
authorizes execution.

## Canonical route

```text
capabilities.constraints
```

## Statuses

- `OBSERVED` — an ability or limitation was noticed but is not yet verified;
- `AVAILABLE` — current capability is source-backed and bounded to its scope;
- `CONSTRAINED` — capability is limited in an explicit context;
- `DISPUTED` — current state is contested and must be held;
- `UNAVAILABLE` — a required resource or capability is currently unavailable;
- `RECOVERED` — a prior constraint no longer supports a current-incapability claim;
- `EXPIRED` — the constraint window has ended;
- `RETIRED` — the capability or constraint is historical, not current;
- `UNKNOWN` — current state is not established.

## Scope model

Every event has an explicit scope:

- `LOCAL`;
- `PROJECT`;
- `CROSS_CONTEXT`.

There is no implicit global or permanent scope. Cross-context current claims
require multiple context references. Identity lesson candidates require
repeated, source-backed, cross-context evidence.

## Event types

- `ABILITY_OBSERVED`;
- `CAPABILITY_VERIFIED`;
- `CONSTRAINT_RECORDED`;
- `RESOURCE_UNAVAILABLE`;
- `CAPABILITY_RECOVERED`;
- `CONSTRAINT_EXPIRED`;
- `CAPABILITY_RETIRED`;
- `CAPABILITY_DISPUTED`;
- `REPEATED_CAPABILITY_VERIFIED`;
- `REPEATED_RECOVERY_VERIFIED`;
- `CURRENT_INCAPABILITY_CLAIM`.

## Source-backed facts

Current capability, constraint, recovery, expiry, retirement, dispute, resource
unavailability, repeated capability/recovery, and current-incapability events
require:

- `knowledge_class=FACT`;
- at least one evidence reference;
- explicit context binding where a current incapability is claimed.

`ABILITY_OBSERVED` may remain memory or inference, but it cannot create a current
incapability claim or identity lesson.

## Current-incapability handling

The center maps current-incapability claims into the Continuity Coordinator:

| Capability status | Result |
|---|---|
| `CONSTRAINED`, `UNAVAILABLE` | bounded current observation when FACT-backed |
| `OBSERVED`, `DISPUTED`, `UNKNOWN` | `HOLD_FOR_REVIEW` |
| `AVAILABLE`, `RECOVERED`, `EXPIRED`, `RETIRED` | `BLOCK_FALSE_PRESENCE` |

A blocked claim remains historical evidence. It does not become current inability.

## Bounded lesson candidates

Only these events may carry identity lesson candidates:

- `REPEATED_CAPABILITY_VERIFIED` with `AVAILABLE` status;
- `REPEATED_RECOVERY_VERIFIED` with `RECOVERED` status.

They require:

- FACT knowledge;
- `CROSS_CONTEXT` scope;
- repeat count of at least two;
- at least two evidence references;
- at least two context references;
- at least two distinct capability observation references.

The output is only a bounded `LessonCandidate`. Stable identity change remains a
separate aggregation and governance operation.

## Authority boundary

Every result explicitly states:

```json
{
  "capability_registry_mutation_allowed": false,
  "access_denial_allowed": false,
  "permanent_incapacity_assignment_allowed": false,
  "training_scheduling_allowed": false,
  "priority_mutation_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

Capability description is not permission. Constraint description is not access
denial. Lesson candidacy is not identity mutation.

## Determinism and replay

The event digest binds the complete event payload. The result ID binds:

- event digest;
- observation digest;
- continuity assessment ID;
- capability policy version.

Identical canonical input produces the same result ID. Replay reconstructs the
same bounded decision without applying capability, access, training, identity,
or execution side effects.

## Non-goals

v0.1 does not:

- infer capability from unverified prose;
- create a permanent capability or incapability registry entry;
- deny a tool or resource;
- schedule training or remediation;
- promote local evidence to global identity;
- authorize work;
- apply an identity update.
