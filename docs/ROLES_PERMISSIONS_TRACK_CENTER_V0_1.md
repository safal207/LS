# LS Roles/Permissions Track Center v0.1

## Purpose

The Roles/Permissions Track Center records evidence about roles, permissions,
delegations, approvals, denials, and authority lifecycle events without becoming
an authorization engine.

Its core invariants are:

> Capability is not permission.
>
> Role membership is not action authorization.
>
> Permission is not delegation.

## Runtime position

```text
roles.permissions envelope
  -> Track Center Router
  -> Roles/Permissions Track Center
  -> TrackObservation(track="roles.permissions")
  -> Continuity Coordinator
  -> ACCEPT_BOUNDED_OBSERVATION | HOLD_FOR_REVIEW | BLOCK_FALSE_PRESENCE
  -> existing Identity Control Plane
```

## Authority status

| Status | Meaning |
|---|---|
| `OBSERVED` | preliminary role signal, not verified authority |
| `ACTIVE` | source-backed authority record is currently active |
| `PENDING_APPROVAL` | action requires approval that is not yet verified |
| `DENIED` | the scoped action is denied |
| `SUSPENDED` | authority is temporarily inactive |
| `REVOKED` | authority was explicitly withdrawn |
| `EXPIRED` | time-bounded authority ended |
| `DISPUTED` | the authority claim is contested |
| `RETIRED` | historical authority only |
| `UNKNOWN` | current authority cannot be established |

## Authority basis

- `ROLE_ASSIGNMENT`
- `DIRECT_PERMISSION`
- `DELEGATION`
- `APPROVAL`
- `POLICY`
- `NONE`
- `UNKNOWN`

Only direct permission, delegation, verified approval, or policy may support a
current-authority claim. A role assignment alone is held for review.

## Current-authority boundary

A current-authority claim is accepted only when all are explicit and verified:

1. status is `ACTIVE`;
2. basis is `DIRECT_PERMISSION`, `DELEGATION`, `APPROVAL`, or `POLICY`;
3. action, resource, and scope are present;
4. knowledge class is `FACT`;
5. evidence, provenance, and execution context are present;
6. an approval-based claim contains an approval reference.

Other claims fail closed:

- role membership without a scoped permission: `HOLD`;
- missing action, resource, scope, evidence, provenance, or context: `HOLD`;
- pending approval, suspension, or dispute: `HOLD`;
- denied, revoked, expired, or retired authority: `BLOCK`.

`BLOCK_FALSE_PRESENCE` here means the old authority record cannot reappear as
current. It is not an access-control decision for an external system.

## Event types

- `ROLE_OBSERVED`
- `ROLE_ASSIGNED`
- `PERMISSION_GRANTED`
- `PERMISSION_DENIED`
- `DELEGATION_RECORDED`
- `APPROVAL_REQUIRED`
- `APPROVAL_VERIFIED`
- `AUTHORITY_SUSPENDED`
- `PERMISSION_REVOKED`
- `AUTHORITY_EXPIRED`
- `AUTHORITY_DISPUTED`
- `AUTHORITY_RETIRED`
- `AUTHORIZATION_PATTERN_VERIFIED`
- `ESCALATION_PATTERN_VERIFIED`
- `CURRENT_AUTHORITY_CLAIM`

Source-backed lifecycle events require `FACT` knowledge, evidence, provenance,
action, resource, and scope.

## Lesson-candidate gate

Only repeated authorization and escalation patterns may carry a bounded lesson.
They require at least two evidence references, two provenance references, two
contexts, two independent observers, and identity scope `roles.permissions`.

A valid lesson may say:

> Escalate when permission scope or approval provenance is incomplete.

It must not grant a role, permission, delegation, approval, or access.

## Authority boundary

Every result states:

```json
{
  "role_registry_mutation_allowed": false,
  "permission_registry_mutation_allowed": false,
  "access_grant_allowed": false,
  "access_denial_allowed": false,
  "approval_allowed": false,
  "delegation_allowed": false,
  "policy_mutation_allowed": false,
  "work_scheduling_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

The center produces reviewable evidence and continuity decisions. Actual
`ALLOW`, `BLOCK`, or `ESCALATE` enforcement remains a separate governed
pre-execution operation.

## Non-goals

v0.1 does not mutate roles or ACLs, grant or deny access, approve changes,
delegate authority, change policy, schedule work, infer authorization from
capability, update stable identity, or execute tools.
