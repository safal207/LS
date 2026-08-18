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

If a current trusted witness presents a valid signature for the same `trust_root_id` and `generation` but a different `snapshot_digest`, the verifier emits:

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
