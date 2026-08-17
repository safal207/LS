# VTL Use-Time Conformance v0.4

This profile makes the `AUTHORIZE -> revalidate -> EXECUTE` boundary portable across agent runtimes.

It is intentionally framework-neutral. An implementation may use its own classes, stores, receipt IDs, worker model, or orchestration engine as long as it produces the same semantic decision for the same vector.

## Normative boundary

The following semantics are normative:

```text
AUTHORIZE != EXECUTE

EXECUTE is emitted only after current reality is compared with the frozen authorization context.
```

The comparison covers:

- exact transition/proposal identity;
- exact source reference;
- exact policy reference;
- exact approval reference;
- complete evidence context;
- approval freshness and expiry;
- exact executor identity;
- a non-empty execution occurrence nonce.

A valid `EXECUTE` receipt is single-use.

## Portable versus implementation-local

The fixture standardizes:

- `EXECUTE | HOLD | BLOCK` verdicts;
- ordered reason codes;
- exact comparison behavior;
- first-use versus replay consumption behavior.

The fixture does **not** standardize a global receipt-ID namespace.

```text
receipt_ids = implementation-local
```

An implementation may map the same semantic decision into its own identifier, storage key, signed envelope, database row, or trace ID.

## Reference vectors

`fixtures/use-time-conformance-v0.4.json` includes nine cases:

1. unchanged context -> `EXECUTE`;
2. source reference drift -> `BLOCK`;
3. policy reference drift -> `BLOCK`;
4. approval reference drift -> `BLOCK`;
5. otherwise changed evidence -> `BLOCK`;
6. approval revoked before use -> `BLOCK`;
7. approval expired before use -> `BLOCK`;
8. executor substitution -> `BLOCK`;
9. missing execution occurrence nonce -> `BLOCK`.

The successful vector also proves the single-use property:

```text
first consume -> true
second consume -> false
```

## Reason-code contract

The current profile uses ordered reason codes because one transition can violate more than one binding.

Examples:

```text
source changed
-> SOURCE_REF_CHANGED
-> EVIDENCE_CONTEXT_CHANGED

policy changed
-> POLICY_REF_CHANGED
-> EVIDENCE_CONTEXT_CHANGED

approval revoked
-> EVIDENCE_CONTEXT_CHANGED
-> APPROVAL_NOT_CURRENT_AT_USE
```

A consumer should preserve all applicable reasons rather than collapsing the result into one opaque denial string.

## JSON Schema

The machine-readable profile is described by:

```text
schemas/use-time-conformance-v0.4.schema.json
```

It uses JSON Schema Draft 2020-12.

The reference Python runtime intentionally has no runtime JSON Schema dependency. The built-in runner performs a small strict shape check, while external implementations may validate against the full schema with their native tooling.

## Running the reference implementation

From `prototypes/verified-transition-loop`:

```bash
python -m pip install -e .
vtl-conformance fixtures/use-time-conformance-v0.4.json
```

A conforming run reports all cases passed and exits with status `0`.

## Adapter contract

To test another runtime, map the fixture fields into that runtime's native concepts:

```text
intent                 -> requested operation
proposal               -> frozen action/state transition
source_ref             -> commit/artifact/version identity
policy_ref             -> policy/config/ruleset identity
approval_ref           -> approval/grant identity
authorization evidence -> evidence captured at decision time
current evidence       -> evidence observed immediately before use
execution_nonce        -> one concrete execution occurrence
```

Then compare the runtime's decision to each vector's `expected` object.

A CrewAI, AutoGen, Codex-style, workflow-engine, or custom implementation can therefore use different internals while proving the same boundary behavior.

## Non-goals

v0.4 does not claim:

- a production authorization system;
- distributed replay protection;
- globally interoperable receipt IDs;
- cryptographic identity for agents or humans;
- external attestation verification;
- authority to perform any side effect.

The next interoperability step can add adapters that translate native runtime evidence into this profile without weakening the core semantic vectors.
