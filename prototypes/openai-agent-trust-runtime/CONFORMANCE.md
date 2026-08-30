# CrossThreadEvent v0.1 Conformance

Run the deterministic fixture:

```bash
ls-cross-thread-conformance
```

The command exits non-zero if any reference case fails.

## Required reference cases

1. Orchestration is permission-gated by default.
2. One thread cannot read another thread's audit without `allow_read`.
3. A delivered event appears in source and target audit views.
4. An unverified state update is deferred and cannot release dependent work.
5. A stale sequence cannot overwrite newer accepted state.
6. Replaying the same `event_id` returns the original decision receipt.
7. An action request is advisory and never means execution occurred.
8. An archived thread cannot send an accepted event.
9. A revoked capability blocks further events.
10. An explicitly resumed thread preserves trajectory state and audit history.

## Exit contract

```json
{
  "protocol": "cross-thread-event/v0.1",
  "ok": true,
  "passed": 10,
  "failed": 0
}
```

This fixture is vendor-neutral and does not require a model or network connection.
