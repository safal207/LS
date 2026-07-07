# Durable Approval Conformance v0.1

## Purpose

This specification defines a vendor-neutral conformance contract for manual approvals in agent runtimes.

The contract prevents requester cancellation, transport loss, UI dismissal, or an elapsed wait window from being misreported as an explicit user rejection.

## Boundary

A durable approval is modeled as:

```text
immutable approval envelope
+ append-only lifecycle events
+ deterministic reducer
= reconstructed multidimensional snapshot
```

The reducer reconstructs four independent dimensions:

```text
authority_state:
  PENDING | APPROVED | REJECTED | EXPIRED | INVALIDATED | LOST

requester_state:
  ATTACHED | DETACHED | CANCELLED

presentation_state:
  NOT_PRESENTED | VISIBLE | DISCONNECTED | RESTORED

execution_state:
  UNUSED | CLAIMED | COMMITTED | FAILED | IN_DOUBT
```

These dimensions MUST NOT be collapsed into one terminal status.

A valid simultaneous snapshot is:

```text
authority_state    = PENDING
requester_state    = CANCELLED
presentation_state = DISCONNECTED
execution_state    = UNUSED
```

## Immutable approval envelope

The envelope binds the authority request to:

- approval, trajectory, continuation, requester, and tool-call identities;
- exact action, scope, policy, workspace, and target-state digests;
- creation time;
- an optional explicit expiry policy;
- single-use execution semantics.

Changing any bound digest requires a new approval.

## Transition ownership

| Transition | Authorized source |
|---|---|
| `PENDING -> APPROVED` | explicit `UserApproved` event from `USER` or authorized `REVIEWER` |
| `PENDING -> REJECTED` | explicit `UserRejected` event from `USER` or authorized `REVIEWER` |
| `PENDING -> EXPIRED` | `ApprovalExpired` from `POLICY`, only when the envelope has an expiry policy |
| `PENDING -> INVALIDATED` | `ApprovalInvalidated` from `RUNTIME` or `VERIFIER`, with evidence |
| any authority state -> `LOST` | `LostStateDetected` from `RUNTIME`, with evidence |

Requester, presentation, and execution events cannot manufacture a user-owned authority resolution.

## ReviewDecision adapter guidance

Runtimes that currently expose a single `ReviewDecision`-style result MUST map source events without collapsing the four dimensions.

| Legacy/runtime signal | Durable event | Authority effect |
|---|---|---|
| authenticated user/reviewer approves the exact bound action | `UserApproved` | `PENDING -> APPROVED` |
| authenticated user/reviewer explicitly rejects | `UserRejected` | `PENDING -> REJECTED` |
| requester future is cancelled or caller stops waiting | `RequesterCancelled` or `RequesterDetached` | none |
| transport/session disconnects | `TransportDisconnected` | none |
| approval surface is closed without an explicit rejection | `UiDismissed` | none |
| local wait window elapses without configured expiry policy | `WaitWindowElapsed` | none |
| configured policy deadline elapses | `ApprovalExpired` | `PENDING -> EXPIRED` |
| exact action, scope, workspace, target, or policy drifts | `ApprovalInvalidated` | `PENDING -> INVALIDATED` |
| durable authority cannot be reconstructed | `LostStateDetected` | authority becomes `LOST`; execution remains blocked |

A legacy `Denied`, `Rejected`, or equivalent terminal value MUST NOT be emitted for cancellation, timeout, disconnect, or UI dismissal. If the adapter cannot distinguish an explicit user decision from lifecycle loss, it MUST fail closed as `LOST` or preserve `PENDING`; it must never synthesize `UserRejected`.

Every authority event must retain the original `approval_id`, actor attribution, and exact action/scope bindings. Execution claiming remains a separate operation.

## Commit before effect

Execution follows:

```text
verify authority_state == APPROVED
-> verify exact action/scope/policy/workspace/target digests
-> append ExecutionClaimed
-> execute side effect
-> append EffectObserved
```

A restart after `ExecutionClaimed` and before `EffectObserved` reconstructs `execution_state = IN_DOUBT`.
The runtime MUST NOT automatically replay the side effect until reconciliation.

## Event ordering

Events are append-only and MUST have:

- unique `event_id`;
- strictly consecutive `sequence` values starting at 1;
- non-decreasing timezone-aware RFC 3339 timestamps;
- actor attribution;
- reason for authority resolution;
- evidence for expiry, invalidation, effect observation, or lost-state resolution.

Duplicate, reordered, contradictory, or ownership-invalid events fail conformance.

## v0.1 fixture set

The initial fixture proves:

1. agent cancellation leaves authority `PENDING`;
2. transport loss leaves authority `PENDING`;
3. UI dismissal without explicit rejection leaves authority `PENDING`;
4. an elapsed wait window without expiry policy leaves authority `PENDING`;
5. only explicit user rejection produces `REJECTED`;
6. explicit approval followed by an execution claim and restart produces `IN_DOUBT`.

## Verification

Run:

```bash
python tools/validate_durable_approval_v0_1.py \
  fixtures/trusted-runtime/durable-approval/pending_approval_not_missing_authority_v0.1.json \
  fixtures/trusted-runtime/durable-approval/envelope.schema.json \
  fixtures/trusted-runtime/durable-approval/event.schema.json

python tools/test_durable_approval_v0_1.py
```

The validator is dependency-free and emits a machine-readable conformance report.
