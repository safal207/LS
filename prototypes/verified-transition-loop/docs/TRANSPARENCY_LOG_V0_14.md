# VTL v0.14 — Transparency Log

VTL v0.14 adds an append-only transparency-log proof above v0.13 witnessed freshness.

## Core separation

```text
witness quorum != log inclusion
signed checkpoint != append-only extension
```

A valid higher layer never repairs an invalid lower layer.

```text
v0.13 witnessed freshness
-> canonical log entry
-> Merkle inclusion proof
-> signed log checkpoint
-> verifier-controlled prior checkpoint
-> Merkle consistency proof
-> peer-checkpoint split-view check
```

## Merkle hashing

v0.14 uses the RFC6962-style domain separation rule over the existing VTL canonical JSON profile:

```text
leaf_hash = SHA256(0x00 || canonical_entry_bytes)
node_hash = SHA256(0x01 || left_hash || right_hash)
```

Canonical profile:

```text
rfc8785-safe-integer/v0.10
```

The tree shape follows the Certificate Transparency Merkle Tree Hash split rule: for a non-singleton tree, split at the largest power of two strictly smaller than the tree size.

## Signed checkpoint

A log checkpoint signs:

```text
checkpoint_id
profile_id
schema_version
canonical_profile
log_id
tree_size
root_hash
issued_at_ms
not_before_ms
not_after_ms
issuer_id
log_authority_id
log_key_id
signature_algorithm
```

The verifier receives `LogAuthority` independently of the checkpoint. Therefore mathematical signature validity remains separate from current key authority:

```text
log_checkpoint_signature_valid
log_checkpoint_authority_valid
log_checkpoint_freshness_valid
```

A revoked or expired log key may still produce `signature_valid=true` while `authority_valid=false`.

## Inclusion

The log entry binds the v0.13-observed trust-root view:

```text
log_id
trust_root_id
snapshot_generation
snapshot_digest
```

`inclusion_valid=true` only when the domain-separated leaf hash and audit path reconstruct the signed checkpoint root at the declared leaf index and tree size.

## Append-only consistency

The verifier retains an independent checkpoint:

```text
known_tree_size
known_root_hash
minimum_tree_size
checkpointed_at_ms
```

For a larger candidate tree, the RFC6962-style consistency path must reconstruct both the old root and the new root. Failure yields:

```text
LOG_CONSISTENCY_PROOF_INVALID
```

For a smaller signed tree:

```text
LOG_CHECKPOINT_ROLLBACK
```

For the same tree size with a different root:

```text
LOG_EQUIVOCATION_DETECTED
```

No Merkle consistency proof can legitimize a same-size root substitution.

## Peer split view

A verifier may also receive other independently observed signed log checkpoints. Only checkpoints with a valid signature, current trusted log authority, current validity interval, and matching `log_id` are eligible as split-view evidence.

If such a peer checkpoint has the same tree size but a different root:

```text
log_equivocation_detected = true
view_consistency_valid = false
valid = false
```

This remains true even when the target leaf has a valid inclusion proof and the candidate tree is a valid append-only extension of the verifier's prior checkpoint.

## Cross-runtime conformance

Machine-readable artifacts:

```text
schemas/transparency-log-v0.14.schema.json
fixtures/transparency-log-v0.14.json
```

Independent implementations:

```text
Python:
  src/verified_transition_loop/transparency_log.py
  src/verified_transition_loop/transparency_log_conformance.py

Node:
  reference/transparency-log-v0.14.mjs
  reference/transparency-log-conformance-v0.14.mjs
```

The fixture contains 26 deterministic cases. Its target snapshot digest is the
exact digest published by the current v0.13 fixture. CI requires Python and Node
to agree on every field of the complete `actual` result for every case.
Canonical entry bytes, leaf hash, checkpoint signed bytes, checkpoint
signature, checkpoint digest, and root hash are independently pinned in the
fixture and every one of those anchors is load-bearing.

Negative vectors include inclusion tamper, malformed paths, consistency
tamper, tree rollback, same-size fork, peer split view, signature/key failures,
stale/future checkpoints, profile/algorithm substitution, and inherited v0.13
failure. Regression gates additionally reject oversized proof paths. Strict
fixture replay also rejects
duplicate JSON keys, unknown or missing fields, dangling or unused variants,
unsafe/missing/no-op mutations, duplicate verification inputs, and partial
expected results. At least one positive case must pass. Merkle indices and tree
sizes retain the full cross-runtime safe-integer domain; the Node verifier does
not use 32-bit bitwise coercion for proof arithmetic.

## Trust ceiling

v0.14 is a reference verification protocol. It does not provide a globally discoverable transparency service, gossip transport, storage durability, global latest-checkpoint consensus, witness discovery, hardware-backed log keys, or Byzantine consensus.

The layer proves only what the supplied evidence can prove:

- the target snapshot is included in the signed tree;
- the signed tree extends the verifier's retained prior tree state;
- supplied trusted peer checkpoints do not expose a same-size conflicting root.

Absence of supplied conflicting evidence is not a proof that no other split view exists globally.
