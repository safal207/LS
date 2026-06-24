# Temporal Orientation Verdict Precedence v0.1

Status: Stable

## Normative order

When more than one fault is present, a conformant implementation MUST return the highest-priority verdict:

```text
REJECT > REVALIDATE > ABSTAIN > RESUME
```

## Required mixed-fault vectors

### Stale continuation + target-state drift

Expected result:

```json
{
  "verdict": "REJECT",
  "reason_code": "CONTINUATION_MISMATCH"
}
```

A continuation mismatch is unsafe and cannot be downgraded to revalidation.

### Target-state drift + incomplete dependency chain

Expected result:

```json
{
  "verdict": "REVALIDATE",
  "reason_code": "TARGET_STATE_DRIFT"
}
```

Authoritative-state drift takes precedence over incomplete recovered context.

## Portability invariant

The order above is part of the public conformance contract. Implementations MUST NOT treat evaluator branch order as incidental.

Executable vectors live in:

```text
fixtures/temporal-orientation/precedence-v0.1.json
```
