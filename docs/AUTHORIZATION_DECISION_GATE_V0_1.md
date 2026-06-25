# LS Authorization Decision Gate v0.1

## Purpose

The Authorization Decision Gate is a deterministic, fail-closed pre-execution
component. It combines governed evidence about capability, scoped authority,
policy, approval, and the current execution context into one decision:

- `ALLOW`
- `BLOCK`
- `ESCALATE`

The gate is not a Track Center and does not update memory or identity.

## Core invariants

> Capability is not permission.
>
> Permission is not execution.
>
> Role membership is not action authorization.
>
> An approval requirement is not approval.
>
> Stale or incomplete context cannot authorize an action.

## Runtime position

```text
Capabilities/Constraints result ----\
Roles/Permissions result ------------+--> evidence adapters
Policy evidence ---------------------+        |
Approval evidence -------------------+        v
Execution-context evidence ----------/  AuthorizationRequest
                                             |
                                             v
                                Authorization Decision Gate
                                  ALLOW | BLOCK | ESCALATE
                                             |
                                             v
                            separate governed execution layer
```

The gate consumes immutable evidence snapshots. It does not read free text to
infer a capability, permission, role, policy, approval, or context.

## Request binding

Every request binds:

- `subject_id`;
- `intent_ref`;
- exact `action`;
- exact `resource`;
- exact `scope_ref`;
- required capability ID;
- capability-to-subject binding reference;
- capability result and Continuity assessment;
- authority result and Continuity assessment;
- policy version and digest;
- approval state and digest;
- execution-context age and digest.

Capability results currently describe a capability rather than its owner. The
adapter therefore requires a separate `subject_binding_ref`. Missing binding is
representable but produces `ESCALATE`; it can never produce `ALLOW`.

All subject-bearing evidence must match the request subject. A cross-subject
mismatch produces `BLOCK`.

## Decision precedence

The gate evaluates decisions in this fixed order:

```text
BLOCK -> ESCALATE -> ALLOW
```

### `BLOCK`

A hard negative fact takes precedence over uncertainty. Examples:

- policy effect is `DENY`;
- authority is `DENIED`, `REVOKED`, `EXPIRED`, or `RETIRED`;
- approval is `DENIED`, `REVOKED`, or `EXPIRED`;
- capability is currently `CONSTRAINED` or `UNAVAILABLE`;
- a capability or authority Continuity assessment is blocked;
- evidence belongs to a different subject.

### `ESCALATE`

The action is not authorized when the evidence is incomplete or uncertain.
Examples:

- capability or authority assessment is held;
- capability-to-subject binding is missing;
- capability is disputed, unknown, or mismatched;
- authority is role-only, pending, suspended, disputed, or unverified;
- authority action/resource/scope does not exactly match the request;
- policy is unknown or applies to another scope;
- required approval is pending, missing, unverified, or not referenced by the
  approval-based authority record;
- execution context is stale, unknown, too old, or scoped differently.

`ESCALATE` means a human or another governed approval mechanism must resolve the
missing evidence. It does not mean “probably allow.”

### `ALLOW`

`ALLOW` requires all of the following:

1. capability assessment is accepted;
2. capability is `AVAILABLE` or `RECOVERED`;
3. capability ID and subject binding match the request;
4. authority assessment is accepted;
5. authority is `ACTIVE` with `DIRECT_PERMISSION`, `DELEGATION`, `APPROVAL`, or
   `POLICY` basis;
6. authority action, resource, and scope match exactly;
7. authority evidence and provenance are present;
8. policy applies to the same action/resource/scope and is `ALLOW`, or is
   `REQUIRE_APPROVAL` with verified approval;
9. approval is verified when required and its ID is bound to approval-based
   authority evidence;
10. execution context is fresh, within its maximum age, and exactly scoped.

## `action_authorized` versus execution

For `ALLOW`, the result contains:

```json
{
  "decision": "ALLOW",
  "action_authorized": true,
  "execution_authorized": false
}
```

`action_authorized` is a semantic decision bound to one immutable
`request_digest`. It is not a reusable bearer token, credential, session, API
key, or tool invocation. The gate does not execute the action.

A downstream execution layer must independently verify the decision ID, request
digest, freshness, single-use rules, and any environment-specific controls.

## Provenance

The deterministic decision ID binds:

- complete authorization request digest;
- final decision;
- ordered reason codes;
- gate policy version.

Result metadata retains the capability result digest, capability subject-binding
reference, authority result digest, policy digest, approval digest, and context
digest.

## Authority boundary

Every result states:

```json
{
  "capability_registry_mutation_allowed": false,
  "role_registry_mutation_allowed": false,
  "permission_registry_mutation_allowed": false,
  "approval_mutation_allowed": false,
  "policy_mutation_allowed": false,
  "context_mutation_allowed": false,
  "work_scheduling_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

## Non-goals

v0.1 does not infer permissions from language, mutate capability or access
registries, grant roles, create approvals, alter policy, refresh context,
schedule work, mint credentials, update identity, invoke tools, or execute an
authorized action.
