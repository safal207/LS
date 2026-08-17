# VTL v0.12 — Cross-Runtime Canonical Trust-Root Snapshot

## Purpose

v0.12 makes the **freshness of trust itself** portable across runtimes.

v0.11 proved that Python and Node can verify the same canonical Ed25519-signed envelope. v0.12 applies the same canonical-byte boundary to the trust-root snapshot that decides whether a signer is still current.

The core invariant is:

```text
valid signature != freshest acceptable authority
```

A historically valid, correctly signed trust-root snapshot can still be rejected because the verifier has already observed a newer generation, because the same generation forks, or because continuity to the verifier's checkpoint is broken.

## Inputs

The detached verifier receives three independent inputs:

```text
signed TrustRootSnapshot
verifier-controlled BootstrapAuthority
verifier-controlled TrustCheckpoint
```

The snapshot producer cannot choose the verifier checkpoint and cannot make its own key trusted merely by embedding it in the snapshot.

## Canonical signed statement

The signed snapshot statement binds:

```text
snapshot_id
profile_id
schema_version
canonical_profile
trust_root_id
policy_version
generation
previous_snapshot_digest
trust_root_digest
issued_at_ms
not_before_ms
not_after_ms
issuer_id
bootstrap_authority_id
bootstrap_key_id
signature_algorithm
```

Canonical profile:

```text
rfc8785-safe-integer/v0.10
```

The snapshot ID is derived from the canonical statement without `snapshot_id`; the Ed25519 signature covers canonical bytes containing the resulting `snapshot_id` plus the complete statement.

The embedded trust root is bound through `trust_root_digest`. Mutating root contents can therefore leave the historical Ed25519 signature mathematically valid while `snapshot_integrity_valid` becomes false.

## Independent claims

The result deliberately exposes separate claims:

```text
snapshot_integrity_valid
canonical_profile_valid
bootstrap_signature_valid
bootstrap_authority_valid
freshness_valid
continuity_valid
valid
```

A higher-layer success never repairs a lower-layer failure.

Examples:

```text
old signed generation:
  bootstrap_signature_valid = true
  continuity_valid = false
  reason = SNAPSHOT_ROLLBACK

same-generation signed fork:
  bootstrap_signature_valid = true
  snapshot_integrity_valid = true
  continuity_valid = false
  reason = SNAPSHOT_FORK_DETECTED

embedded root payload tamper:
  bootstrap_signature_valid = true
  snapshot_integrity_valid = false
  reason = TRUST_ROOT_DIGEST_MISMATCH
```

## Checkpoint semantics

The checkpoint can contain:

```text
minimum_generation
known_generation
known_snapshot_digest
checkpointed_at_ms
trust_root_id
```

When a known generation and digest exist:

```text
snapshot.generation < known_generation
  -> SNAPSHOT_ROLLBACK

snapshot.generation == known_generation && digest differs
  -> SNAPSHOT_FORK_DETECTED

snapshot.generation == known_generation + 1 && predecessor differs
  -> PREVIOUS_SNAPSHOT_DIGEST_MISMATCH

snapshot.generation > known_generation + 1
  -> SNAPSHOT_CONTINUITY_GAP
```

A checkpoint from the future or an incomplete `(known_generation, known_snapshot_digest)` pair fails closed.

## Cross-runtime proof

Independent implementations:

```text
Python:
  src/verified_transition_loop/canonical_trust_snapshot.py
  src/verified_transition_loop/canonical_trust_snapshot_conformance.py

Node:
  reference/canonical-runtime-v0.12.mjs
  reference/canonical-trust-root-snapshot-v0.12.mjs
```

Both consume the same machine-readable fixture:

```text
fixtures/canonical-trust-root-snapshot-v0.12.json
schemas/canonical-trust-root-snapshot-v0.12.schema.json
```

CI requires complete structured equality:

```text
Python result == Node result
```

and independently checks the exact canonical signed bytes, Ed25519 signature, and full signed-snapshot digest for the fresh reference case.

## Shared vectors

The v0.12 profile contains 20 cases covering:

- fresh valid snapshot;
- bad signature;
- unknown bootstrap key;
- ambiguous bootstrap key;
- malformed bootstrap key material;
- revoked bootstrap key;
- expired snapshot;
- not-yet-valid / future-issued snapshot;
- generation floor;
- rollback of a valid historical snapshot;
- same-generation signed fork;
- wrong predecessor digest;
- continuity gap;
- trust-root ID mismatch;
- policy-version mismatch;
- canonical-profile mismatch;
- embedded root payload tamper;
- future checkpoint;
- incomplete checkpoint state;
- algorithm substitution.

## Compatibility

v0.12 is opt-in. It does **not** rewrite v0.9 snapshot identities or historical v0.8/v0.11 signatures. Earlier profiles remain independently executable.

## Trust ceiling

v0.12 proves deterministic cross-runtime verification relative to verifier-controlled bootstrap and checkpoint state. It does not provide a globally available latest-generation oracle, witness quorum, transparency-log inclusion, hardware-backed checkpoint storage, or distributed consensus over trust-root freshness.
