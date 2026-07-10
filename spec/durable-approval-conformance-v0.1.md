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

## Reviewer authorization trust boundary

LS v0.1 chooses a **trusted upstream event boundary** for reviewer authorization.

The frozen v0.1 event contract validates event shape, actor ownership, ordering, bindings, and deterministic state transitions. It does not carry reviewer credentials, signatures, registry proofs, or policy-lookup results.

The normative trust contract is:

> LS v0.1 trusts reviewer identity supplied by the authenticated upstream CI runtime. Inputs originating from pull-request-controlled content are not considered trusted reviewer identity.

Within this boundary, `actor.type == REVIEWER` is sufficient only when all of the following are true:

- the lifecycle event is emitted by an already-authenticated trusted runtime or event-store producer;
- that producer has authorized `actor.id` before appending the event;
- reviewer identity is derived from trusted platform identity context, not copied from event payload text;
- the authenticated identity source and authorization decision remain auditable in producer provenance;
- the appended event is immutable, and downstream consumers do not rewrite `actor.type` or `actor.id`.

The following sources are untrusted for reviewer identity and MUST NOT authorize a `REVIEWER` event by themselves:

- pull-request title, body, diff, comments, labels, or branch-controlled files;
- issue text or other user-authored repository content;
- artifact metadata, fixture content, model/tool output, or free-form evidence text;
- environment variables or workflow inputs controllable by the pull request;
- `reason`, `evidence_ref`, bindings, or any other lifecycle-event field outside `actor`.

A producer receiving an event from an external or pull-request-controlled source MUST authenticate and normalize it before it enters the trusted append-only event stream. A raw payload that merely declares `actor.type = REVIEWER` is outside the v0.1 trust boundary and MUST NOT be accepted as proof of reviewer authorization.

### Threat model

| Threat | v0.1 control |
|---|---|
| Payload text claims that a reviewer approved | Identity is taken only from the authenticated producer context; text fields cannot override actor ownership. |
| An `AGENT` or other unauthorized actor emits `UserApproved` / `UserRejected` | Deterministic validation rejects the event using the event-owner matrix. |
| A pull request directly supplies `actor.type = REVIEWER` | The producer boundary must reject or re-authenticate the payload before append; the wire validator alone does not prove authorization. |
| A downstream stage rewrites reviewer identity | Lifecycle events are immutable and append-only; provenance must preserve the original producer identity. |
| The authenticated runtime or event store is compromised | Out of scope for the v0.1 wire contract; deployment security and provenance controls must surface this boundary explicitly. |

This decision resolves [#822](https://github.com/safal207/LS/issues/822) for the v0.1 release sequence tracked by [Epic #846](https://github.com/safal207/LS/issues/846). In-band reviewer authorization evidence remains a possible future contract version and is not implied by v0.1 conformance.

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
