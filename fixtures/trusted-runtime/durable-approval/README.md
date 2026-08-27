# Durable approval fixtures

This directory contains vendor-neutral conformance artifacts for manual approval ownership and execution reconciliation.

## Product demo

Run the executable product walkthrough:

```bash
python tools/demo_approval_integrity.py
```

See `docs/product/approval-integrity-30-second-demo.md` for the user-facing scenario and integration direction.

## Frozen wire contracts

- `envelope.schema.json` — immutable approval bindings (`ls-durable-approval-envelope-v0.1`).
- `event.schema.json` — append-only lifecycle events (`ls-approval-lifecycle-event-v0.1`).

The wire contracts remain unchanged across conformance suites v0.1 and v0.2.

## Conformance suite v0.1

- `pending_approval_not_missing_authority_v0.1.json`
- `tools/validate_durable_approval_v0_1.py`
- `tools/test_durable_approval_v0_1.py`

Boundary:

```text
requester cancellation / transport loss / elapsed local wait
!= explicit user rejection
```

## Conformance suite v0.2

- `configured_policy_expiry_v0.2.json`
- `verified_context_invalidation_v0.2.json`
- `durable_state_loss_v0.2.json`
- `reconcile_in_doubt_committed_v0.2.json`
- `reconcile_in_doubt_failed_v0.2.json`
- `tools/validate_durable_approval_v0_2.py`
- `tools/test_durable_approval_v0_2.py`

Boundary:

```text
terminal authority resolution
!= execution reconciliation
```

v0.2 proves that `EXPIRED`, `INVALIDATED`, and `LOST` have distinct owners and evidence, while `IN_DOUBT` resolves only through attributed effect observation. Single-use execution claims cannot be replayed after restart, failure, or a committed effect.

See:

- `spec/durable-approval-conformance-v0.1.md`
- `spec/durable-approval-conformance-v0.2.md`
- `CONFORMANCE.md`
