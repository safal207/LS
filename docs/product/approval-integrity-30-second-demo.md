# LS Approval Integrity — 30-second product demo

## Product promise

> An AI agent cannot lose, invent, or reuse the user's approval.

The first product scenario is intentionally narrow:

```text
The user is reviewing an action
→ the requester stops waiting or transport disconnects
→ the user's authority remains PENDING
→ nothing executes
→ no rejection is attributed to the user
```

## Run the demo

From the repository root:

```bash
python tools/demo_approval_integrity.py
```

Machine-readable output:

```bash
python tools/demo_approval_integrity.py --json
```

CI contract:

```bash
python tools/demo_approval_integrity.py --check
```

## What the viewer sees

### Without an integrity contract

```text
Message: Approval not granted
Risk: requester termination is collapsed into a user authority outcome
```

The user did not reject the action. The system nevertheless loses or misreports the user's decision state.

### With LS Approval Integrity

```text
Your decision is still pending.
The agent stopped waiting.
Nothing was executed.

Authority:    PENDING
Requester:    CANCELLED
Presentation: VISIBLE
Execution:    UNUSED
```

## Why this is a product, not only a specification

The demo gives an agent platform three immediately usable capabilities:

1. a stable runtime status that survives requester cancellation and transport loss;
2. user-facing language that never attributes an unmade decision to the user;
3. an execution gate that remains closed until exact authority is validly claimed.

The conformance fixture, reducer, and CI check make that product promise regression-testable.

## Executable evidence

The demo is reconstructed from the canonical conformance fixture rather than hard-coded as a screenshot.

It fails when any of these promises stop being true:

- requester cancellation manufactures `UserRejected`;
- requester cancellation resolves authority;
- transport loss resolves authority;
- execution changes from `UNUSED` without a valid claim.

The underlying conformance suites additionally cover:

- explicit user approval and rejection;
- configured policy expiry;
- verified context invalidation;
- durable-state loss;
- exact action/scope binding;
- single-use execution claims;
- restart reconciliation through `IN_DOUBT`.

## Product surface

The internal reducer has four independent dimensions, but the user-facing language stays simple:

| Runtime state | User-facing message |
|---|---|
| authority `PENDING`, requester `CANCELLED` | Your decision is still pending. The agent stopped waiting. |
| authority `PENDING`, presentation `DISCONNECTED` | Connection lost. Your pending decision was preserved. |
| authority `INVALIDATED` | The action changed. Review and approve the new version. |
| execution `IN_DOUBT` | Approval was claimed, but execution is being verified. |
| authority `LOST` | Approval state could not be verified. Nothing further will execute without a new decision. |

## Integration direction

The product path is:

```text
agent adapter
→ immutable approval envelope
→ append-only lifecycle events
→ deterministic reducer
→ execution gate
→ user-safe status
```

This demo is the smallest vertical slice of the future **LS Approval Integrity Runtime**: a vendor-neutral trust layer for coding agents, MCP tools, CI automation, and other systems that request consequential human approval.
