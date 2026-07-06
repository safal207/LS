# Durable approval fixtures

This directory contains vendor-neutral conformance artifacts for manual approval ownership.

## v0.1

- `envelope.schema.json` — immutable approval bindings.
- `event.schema.json` — append-only lifecycle event contract.
- `pending_approval_not_missing_authority_v0.1.json` — canonical fixture derived from `openai/codex#29627`.

The reference reducer lives at:

```text
tools/validate_durable_approval_v0_1.py
```

The initial boundary is:

```text
requester cancellation / transport loss / elapsed local wait
!= explicit user rejection
```

See `spec/durable-approval-conformance-v0.1.md` for transition ownership and commit-before-effect rules.
