# VTL v0.9 — Rollback-Resistant Trust-Root Snapshots

VTL v0.8 can verify an attested dispatch against a verifier-supplied trust root. v0.9 verifies a different claim:

> Is that trust root itself authentic, fresh enough, and continuous with what this verifier already knows?

```text
out-of-band bootstrap authority
-> signed TrustRootSnapshot generation N
-> verifier-controlled TrustCheckpoint
-> fresh v0.8 trust-root payload
-> v0.8 attested dispatch verification
```

The snapshot does not get to define the bootstrap key or the verifier checkpoint that makes it authoritative/current.

## Independent result dimensions

The detached verifier returns:

```text
snapshot_integrity_valid
bootstrap_signature_valid
bootstrap_authority_valid
freshness_valid
continuity_valid
```

A mathematically valid signature on an old snapshot remains a valid historical signature while rollback protection can still reject the snapshot.

## Snapshot binding

The signed statement binds:

```text
snapshot_id
profile_id
schema_version
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

`trust_root_digest` binds the complete v0.8 trust-root payload. `snapshot_id` is derived from the statement fields excluding the signature.

The verifier accepts only the published fields for the snapshot, bootstrap authority, bootstrap key, checkpoint, and embedded v0.8 trust root. Duplicate JSON member names (including escaped-name collisions), non-finite values, unpublished fields, negative epoch times, and invalid verifier time fail closed before signature, freshness, or continuity claims are evaluated. This prevents ignored properties from being presented downstream as though they were signed or verifier-authorized claims.

## Verifier-controlled inputs

### Bootstrap authority

The bootstrap authority supplies the Ed25519 public key(s) that may sign snapshots. It is external input and cannot be supplied by the snapshot being verified.

### Trust checkpoint

The checkpoint supplies an independently retained freshness floor:

```text
trust_root_id
minimum_generation
known_generation
known_snapshot_digest
checkpointed_at_ms
```

The known generation/digest pair is optional. With only `minimum_generation`, the verifier gets rollback resistance below a floor. With a known generation/digest, the verifier additionally gets same-generation fork detection and direct next-generation continuity checking.

## Continuity rules

Given checkpoint `(known_generation=K, known_snapshot_digest=D)`:

```text
snapshot generation < K      -> SNAPSHOT_ROLLBACK
snapshot generation = K      -> digest must equal D, otherwise SNAPSHOT_FORK_DETECTED
snapshot generation = K + 1  -> previous_snapshot_digest must equal D
snapshot generation > K + 1  -> SNAPSHOT_CONTINUITY_GAP
```

Re-verifying the exact checkpointed snapshot is allowed. Skipping unobserved generations is not silently treated as continuous.

## Executable v0.9 profile

The reference fixture contains 14 snapshot vectors:

```text
valid fresh snapshot                               -> PASS
bad snapshot signature                             -> FAIL
unknown bootstrap key                              -> FAIL
trust-root payload tamper                          -> FAIL
expired snapshot                                   -> FAIL
not-yet-valid snapshot                             -> FAIL
generation below verifier floor                    -> FAIL
old signed snapshot after newer checkpoint         -> FAIL
same generation / different digest fork            -> FAIL
wrong previous snapshot digest                     -> FAIL
trust-root id mismatch                             -> FAIL
policy-version mismatch                            -> FAIL
bootstrap algorithm substitution                   -> FAIL
continuity gap                                     -> FAIL
```

A separate layered regression proves that a valid/fresh snapshot cannot rescue an invalid v0.8 attestation.

## CLI

```bash
vtl-trust-root-verify snapshot.json \
  --bootstrap-authority bootstrap-authority.json \
  --checkpoint checkpoint.json \
  --now-ms 1800000001000
```

Run the deterministic conformance fixture:

```bash
vtl-trust-root-verify fixtures/trust-root-snapshot-v0.9.json
```

## Trust ceiling

The reference profile protects against rollback/fork relative to a verifier-controlled local checkpoint and bootstrap authority. It does not provide a global consensus source for the latest generation, transparency-log inclusion, remote witness quorum, hardware-backed checkpoint storage, or online distribution of revocation/freshness state.

Those can be layered later without changing the key invariant:

> **A signed trust root is not automatically the freshest trust root the verifier is entitled to accept.**
