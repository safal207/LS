# VTL v0.13 — Witnessed Freshness

VTL v0.13 adds an independent witness layer above v0.12 trust-root freshness.

The problem it addresses is **split view / equivocation**:

```text
Verifier A sees signed history X
Verifier B sees signed history Y
X and Y are each locally valid
but X != Y at the same trust-root generation
```

A local checkpoint alone cannot prove that another verifier was not shown a different signed view.

## Core invariant

```text
locally fresh + correctly signed != globally non-equivocated
```

v0.13 therefore verifies a quorum of independently trusted witness statements about the observed trust-root view.

## Witness statement

Each statement binds:

```text
profile_id
schema_version
canonical_profile
trust_root_id
generation
snapshot_digest
observed_at_ms
witness_id
witness_key_id
signature_algorithm
```

`statement_id` is the SHA-256-derived identity of the canonical statement fields. The Ed25519 signature covers `statement_id` plus the canonical statement.

Canonicalization profile:

```text
rfc8785-safe-integer/v0.10
```

## Verifier-controlled witness authority

Witness authority is external input to the verifier. It supplies:

```text
quorum
max_statement_age_ms
allowed_algorithms
trusted witness keys
key validity intervals
revocation state
```

The producer cannot declare its own witnesses trusted.

Before evaluating any claim, each reference verifier takes one deep snapshot of
the target view, witness statements, and verifier-controlled authority. Caller
mutation after that boundary cannot mix evidence from two moments into one
verdict. Snapshot, authority, key, and statement objects use exact published
field sets; unpublished fields fail closed instead of becoming unsigned claims.

All generations and epoch-millisecond values are non-negative safe integers.
Witness signatures must be canonical base64 encodings of exactly 64 Ed25519
signature bytes, and trusted public keys must decode canonically to exactly 32
bytes before they can support a signature or authority claim.

## Separate claims

The verifier does not collapse all trust into one boolean:

```text
local_snapshot_valid
witness_statement_integrity_valid
witness_signature_valid
witness_authority_valid
witness_freshness_valid
witness_quorum_valid
view_consistency_valid
equivocation_detected
valid
```

A mathematically valid witness signature may still fail authority or freshness. A sufficient quorum may still fail the whole proof when a valid conflicting view is present.

## Quorum semantics

Quorum counts **unique witness identities only**. Repeating the same witness statement never increases quorum.

A witness counts toward the target view only when all of these are true:

1. statement shape/profile/canonical identity is valid;
2. Ed25519 signature verifies;
3. witness key is uniquely trusted, current, unrevoked, and algorithm-compatible;
4. statement is within the configured freshness window;
5. `trust_root_id`, `generation`, and `snapshot_digest` exactly match the target snapshot view.

## Equivocation

If a conforming, current trusted witness presents a valid signature for the same `trust_root_id` and `generation` but a different `snapshot_digest`, the verifier emits:

```text
WITNESS_SNAPSHOT_DIGEST_MISMATCH
EQUIVOCATION_DETECTED
```

This blocks the proof even if enough other witnesses still satisfy quorum for the target digest.

## Compatibility

v0.13 consumes the result of the v0.12 local snapshot verifier as a lower-layer claim. It does not repair or reinterpret v0.12 failures.

```text
v0.12 local canonical trust snapshot
-> witnessed view
-> v0.13 quorum / split-view verification
```

A valid witness quorum cannot rescue `local_snapshot_valid=false`.

The deterministic v0.13 fixture binds its `snapshot_view.snapshot_digest` to
the exact `expected_fresh_snapshot_digest` published by the current v0.12
fixture. v0.13 consumes the already-established lower-layer boolean; it does not
rerun v0.12, infer a newer checkpoint, or widen any v0.12 claim.

## Reference implementations

Python:

```text
src/verified_transition_loop/witnessed_freshness.py
src/verified_transition_loop/witnessed_freshness_conformance.py
```

Node:

```text
reference/witnessed-freshness-v0.13.mjs
```

Shared artifacts:

```text
schemas/witnessed-freshness-v0.13.schema.json
fixtures/witnessed-freshness-v0.13.json
```

The fixture contains 20 deterministic vectors covering quorum, duplicates, key trust/revocation/expiry, signature failure, stale/future statements, root/generation/digest mismatch, split-view equivocation, malformed/ambiguous keys, canonical-profile substitution, local v0.12 failure, and quorum configuration.

Both conformance runners use strict duplicate-key-aware JSON parsing, snapshot
the complete fixture before validation, require exact root/case/expected fields,
and compare every independent result claim. Case identifiers must be unique,
all named statements must be referenced, and mutation paths must exist, change
their target, stay within bounds, and exclude prototype-control names. A suite
whose vectors all describe invalid results can never report `all_passed=true`.

## Trust ceiling

v0.13 is a reference verification layer, not a globally consistent transparency service. It proves consistency only relative to the witness authority and witness evidence supplied to the verifier.

It does **not** provide:

- automatic witness discovery;
- a globally latest checkpoint oracle;
- Byzantine consensus;
- append-only transparency-log inclusion proofs;
- gossip transport between verifiers;
- hardware-backed witness keys;
- production execution authority.

Those are possible later layers and must not be implied by a successful v0.13 result.
