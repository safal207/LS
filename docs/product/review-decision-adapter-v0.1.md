# LS ReviewDecision Adapter v0.1

## Product promise

> The adapter never invents a user decision.

Many agent runtimes expose a single coarse result such as `approved`, `denied`, or `approval_not_granted`. That representation loses the distinction between:

- the user resolving authority;
- the requester stopping its wait;
- the approval UI disappearing;
- the transport disconnecting;
- an execution being claimed or completed.

The LS adapter converts a compact runtime signal into a safe multidimensional projection.

## 30-second scenario

```text
The user is still reviewing an action
→ the requesting tool future is cancelled
```

A coarse adapter may report:

```text
APPROVAL_NOT_GRANTED
```

That status is ambiguous and can be interpreted as a user decision.

LS projects:

```text
authority_state    = PENDING
requester_state    = CANCELLED
presentation_state = VISIBLE
execution_state    = UNUSED
outward_status     = WAITING_FOR_USER
```

User-facing message:

> Your decision is still pending. The agent stopped waiting. Nothing was executed.

## Run

Validate the canonical fixture:

```bash
python tools/review_decision_adapter_v0_1.py --check
```

Render the product demo:

```bash
python tools/review_decision_adapter_v0_1.py --demo
```

Print the complete machine-readable report:

```bash
python tools/review_decision_adapter_v0_1.py
```

Run negative controls:

```bash
python tools/test_review_decision_adapter_v0_1.py
```

## Input contract

```json
{
  "approval_id": "approval-001",
  "signal": "REQUESTER_CANCELLED",
  "actor": {
    "type": "AGENT",
    "id": "agent-root"
  },
  "reason": "requesting future cancelled",
  "evidence_ref": null,
  "exact_bindings_match": true,
  "expiry_policy_configured": false
}
```

Supported signals:

| Signal | Durable event | Authority effect |
|---|---|---|
| `USER_APPROVED` | `UserApproved` | `PENDING → APPROVED` |
| `USER_REJECTED` | `UserRejected` | `PENDING → REJECTED` |
| `REQUESTER_CANCELLED` | `RequesterCancelled` | none |
| `REQUESTER_DETACHED` | `RequesterDetached` | none |
| `TRANSPORT_DISCONNECTED` | `TransportDisconnected` | none |
| `UI_DISMISSED` | `UiDismissed` | none |
| `WAIT_WINDOW_ELAPSED` | `WaitWindowElapsed` | none |
| `POLICY_EXPIRED` | `ApprovalExpired` | `PENDING → EXPIRED` |
| `CONTEXT_INVALIDATED` | `ApprovalInvalidated` | `PENDING → INVALIDATED` |
| `STATE_LOST` | `LostStateDetected` | authority becomes `LOST` |

## Output contract

The adapter returns:

```json
{
  "valid": true,
  "errors": [],
  "projection": {
    "durable_event_type": "RequesterCancelled",
    "authority_state": "PENDING",
    "requester_state": "CANCELLED",
    "presentation_state": "VISIBLE",
    "execution_state": "UNUSED",
    "outward_status": "WAITING_FOR_USER",
    "user_message": "Your decision is still pending. The agent stopped waiting. Nothing was executed.",
    "execution_blocked": true,
    "execution_claim_allowed": false,
    "resolution": null
  }
}
```

## Fail-closed behavior

The adapter returns `ADAPTER_ERROR`, keeps authority `PENDING`, keeps execution `UNUSED`, and blocks execution when:

- a signal is unsupported or ambiguous;
- an actor is not allowed to emit the signal;
- an approval does not match the exact reviewed bindings;
- an expiry has no configured policy;
- expiry, invalidation, or durable-state loss lacks evidence;
- the input contains unknown fields.

It never guesses that an ambiguous `denied`-like value means `UserRejected`.

## Integration boundary

```text
Codex-style runtime signal
→ ReviewDecision adapter
→ durable lifecycle event
→ multidimensional projection
→ execution gate + user-safe message
```

The adapter does not execute the action. `USER_APPROVED` only permits a separate exact-binding execution claim. All other signals keep execution blocked.

## Canonical evidence

The fixture `review_decision_adapter_cases_v0.1.json` contains ten positive vectors. Mutation tests additionally prove:

- an agent cannot manufacture user rejection;
- mismatched bindings cannot produce approval;
- implicit expiry is rejected;
- missing evidence is rejected;
- unsupported coarse statuses fail closed;
- duplicate fixture cases are rejected;
- projection is deterministic.

This prototype builds on the merged Durable Approval conformance runtime from PR #796 and the external authorization-state discussion in `openai/codex#29627`.
