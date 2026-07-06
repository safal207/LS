# Durable Approval Conformance v0.2

## Status

This suite extends v0.1 without changing the frozen v0.1 envelope or lifecycle-event wire contracts.

```text
conformance suite v0.2
uses
DurableApprovalEnvelope v0.1
+ ApprovalLifecycleEvent v0.1
```

## Purpose

v0.1 proved that requester cancellation, transport loss, and an elapsed local wait cannot manufacture user rejection or expiry.

v0.2 adds deterministic terminal-resolution and reconciliation coverage:

- configured policy expiry;
- verified context invalidation;
- explicit durable-state loss;
- restart after execution claim;
- reconciliation of `IN_DOUBT` to `COMMITTED` or `FAILED`;
- rejection of duplicate or replayed execution claims.

## Terminal authority ownership

| Authority result | Required event | Required actor | Required evidence |
|---|---|---|---|
| `EXPIRED` | `ApprovalExpired` | `POLICY` | expiry-policy evidence |
| `INVALIDATED` | `ApprovalInvalidated` | `RUNTIME` or `VERIFIER` | context-drift evidence |
| `LOST` | `LostStateDetected` | `RUNTIME` | durable-state-loss evidence |

`LOST` is not rejection. It means that authority cannot be reconstructed safely and therefore cannot authorize execution.

## Reconciliation

After an approved authority is atomically claimed:

```text
APPROVED + UNUSED
-> ExecutionClaimed
-> CLAIMED
```

A runtime restart before an effect observation produces:

```text
CLAIMED
-> RuntimeRestarted
-> IN_DOUBT
```

Only an attributed reconciliation event may resolve the execution dimension:

```text
IN_DOUBT
-> EffectObserved(outcome=COMMITTED)
-> COMMITTED
```

or:

```text
IN_DOUBT
-> EffectObserved(outcome=FAILED)
-> FAILED
```

The original authority remains `APPROVED`; reconciliation answers whether the bound effect occurred. It does not issue new authority.

## Single-use invariant

An approval envelope with `single_use=true` permits at most one valid `ExecutionClaimed` event.

A second claim fails conformance even when:

- the action digest is identical;
- the first attempt is `IN_DOUBT`;
- the first effect is later observed as failed;
- the process restarted;
- another tool or continuation submits the claim.

Retry requires a new approval envelope or a separate policy-defined reconciliation operation that does not replay the side effect.

## Verification

Run:

```bash
python tools/validate_durable_approval_v0_2.py \
  fixtures/trusted-runtime/durable-approval/full_lifecycle_v0.2.json \
  fixtures/trusted-runtime/durable-approval/envelope.schema.json \
  fixtures/trusted-runtime/durable-approval/event.schema.json

python tools/test_durable_approval_v0_2.py
```

The output separates authority resolution from execution reconciliation and remains deterministic under replay.
