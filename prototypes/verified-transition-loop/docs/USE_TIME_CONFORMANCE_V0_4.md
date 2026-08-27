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

`approval_valid_until_ms` is an exclusive upper bound: an approval is expired
when the use-time clock is equal to or later than that value.

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

`fixtures/use-time-conformance-v0.4.json` includes ten cases:

1. unchanged context -> `EXECUTE`;
2. source reference drift -> `BLOCK`;
3. policy reference drift -> `BLOCK`;
4. approval reference drift -> `BLOCK`;
5. otherwise changed evidence -> `BLOCK`;
6. approval revoked before use -> `BLOCK`;
7. approval expired before use -> `BLOCK`;
8. executor substitution -> `BLOCK`;
9. missing execution occurrence nonce -> `BLOCK`;
10. proposal / transition identity drift -> `BLOCK` with `AUTHORIZATION_TRANSITION_MISMATCH`.

The successful vector also proves the single-use property:

```text
first consume -> true
second consume -> false
```

The proposal-drift vector deliberately keeps current evidence stable while changing the transition identity. This prevents an implementation from claiming conformance while ignoring the frozen proposal binding.

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

proposal identity changed
-> AUTHORIZATION_TRANSITION_MISMATCH
```

A consumer should preserve all applicable reasons rather than collapsing the result into one opaque denial string.

## JSON Schema and strict reference validation

The machine-readable profile is described by:

```text
schemas/use-time-conformance-v0.4.schema.json
```

It uses JSON Schema Draft 2020-12.

The reference Python runtime intentionally has no runtime JSON Schema dependency, but its built-in validator enforces the contract it consumes **strictly** before execution:

- exact object keys / rejection of unknown properties;
- nested required fields;
- primitive types without `str()` / `int()` coercion;
- non-negative integer bounds;
- enum values;
- non-empty and unique proposal invariants;
- optional case-level proposal override using the same proposal shape.

External implementations may additionally validate against the published JSON Schema with their native tooling.

## Running the reference implementation

From `prototypes/verified-transition-loop`:

```bash
python -m pip install -e .
vtl-conformance fixtures/use-time-conformance-v0.4.json
```

A conforming run reports all ten cases passed and exits with status `0`.

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

Then compare the runtime's decision to each applicable vector's `expected` object.

A framework adapter may enforce an invariant earlier than the portable core. For example, a runtime whose required occurrence identifier is itself the execution nonce can reject a missing occurrence before reaching the generic `EXECUTION_NONCE_INVALID` path. Likewise, a framework-generated proposal can prove proposal binding through immutable request binding instead of accepting a synthetic case-level proposal override. Such adapter-specific early rejection does not weaken the portable core oracle; the portable profile remains the normative semantic reference.

## Non-goals

v0.4 does not claim:

- a production authorization system;
- distributed replay protection;
- globally interoperable receipt IDs;
- cryptographic identity for agents or humans;
- external attestation verification;
- authority to perform any side effect.

Adapters translate native runtime evidence into this profile without weakening its core semantic vectors.
