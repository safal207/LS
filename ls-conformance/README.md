# LS Conformance Catalog

This folder contains portable conformance fixture families for agent runtimes, memory layers, governance systems, and external clients.

The goal is not to require adoption of LS as a full framework. The goal is to provide small, reusable failure-mode fixtures and invariants that other projects can adapt independently.

## Flagship fixture families

1. [`missed_terminal_event_reconciliation`](./missed_terminal_event_reconciliation/README.md)
   - bounded recovery after a client misses a committed terminal event.

2. [`durable_memory_not_authority`](./durable_memory_not_authority/README.md)
   - durable memory may orient, but cannot authorize action without explicit authority.

3. [`credential_bound_tool_authority`](./credential_bound_tool_authority/README.md)
   - constrained tool calls must not reach upstream execution without a valid credential bound to the exact call.

4. [`product_traceability`](./product_traceability/README.md)
   - implementation and verification do not become active product state without an exact hypothesis binding and confirmed outcome evidence.

5. [`profit_traceability`](./profit_traceability/README.md)
   - product activity and attributable revenue do not become a scale decision without confirmed unit economics and positive net contribution.

## Shared invariants

- Truth is not authority.
- Memory is not permission.
- Audit can outlive authority.
- Resume is not replay.
- Completeness is phase-relative.
- Verification is not success.
- Implementation is not outcome.
- Revenue is not profit.
- Attribution is not causation.
- Pending approval is not missing approval.
- Credential is not receipt.
- Fail closed on missing authority, terminal proof, credential, approval resolution, outcome evidence, economic evidence, or revalidation.

## Relationship to LS Conformance Pack v0.1

Canonical issue: https://github.com/safal207/LS/issues/757
