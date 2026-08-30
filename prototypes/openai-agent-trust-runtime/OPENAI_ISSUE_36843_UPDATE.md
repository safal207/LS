# Suggested update for openai/codex#36843

An executable vendor-neutral reference fixture is now available in LS.

Implemented:

- `CrossThreadEvent v0.1` JSON Schema;
- receiver-side `CapabilityGrant` with event-type, read, consent, expiry, revocation, and authority limits;
- evidence checking distinct from sender verification claims;
- `ACCEPTED / DEFERRED / REJECTED` decision receipts;
- stale-state rejection and event-id idempotency;
- archived/resumed thread lifecycle with preserved trajectory history;
- hash-chained audit visible to both peers under capability rules;
- a deterministic ten-case conformance runner;
- a seven-agent reference council: Idea, Customer, Consumer, Designer, Executor, Stabilizer, Innovator.

Reproduction:

```bash
cd prototypes/openai-agent-trust-runtime
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ls-cross-thread-conformance
ls-cross-thread-demo
```

The implementation remains advisory-only and never executes merge, deploy, payment, deletion, messaging, or permission changes.
