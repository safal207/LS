# LS Continuity Store v0.1

A minimal, local continuity store for trustworthy agent runtimes.

It does **not** attempt to persist an agent's consciousness or full working memory. It persists the verifiable conditions under which an interrupted action may safely continue.

## Core invariants

- `memory != authority`
- `communication != continuity`
- `decision != outcome`
- `authorization != retry eligibility`
- `pending approval != deny`
- `index != evidence`
- `snapshot != live permission`
- `historical execution != retry eligibility`
- `response honesty != action authorization`
- `causal validity != execution success`

## Storage model

1. Every record is canonicalized with RFC 8785 JCS.
2. Its identifier is `sha256(canonical_bytes)`.
3. The object is written immutably under a content-addressed path.
4. An append-only hash-chained event is recorded in SQLite WAL.
5. A rebuildable current-state projection is updated.
6. Recovery verifies objects, event hashes, replay, and projection equality.

## Quick start

Requires Node.js 22.5+ because the prototype uses the built-in `node:sqlite` module.

```bash
npm install
npm run build
npm test
npm run demo
npm run demo:transition
```

Node.js may print an experimental SQLite warning; that is expected for this v0.1 prototype.

## Object path

```text
data/objects/<first-2>/<next-2>/<full-digest>.json
```

## Resume policy

`evaluateResume()` returns fail-closed results for:

- pending approval;
- expired or invalidated authority;
- consumed authority;
- context requiring revalidation;
- non-retryable operations.

## Trustworthy-transition continuity adapter

`trustworthy-transition.ts` stores a transition snapshot as an immutable
`verification_receipt`. The snapshot binds:

```text
transition_id
subject_id
action_identity_digest
binding_digest
authorization_ref
observation_refs
response_integrity_ref
causal_audit_ref
context_digest
```

It preserves these independent dimensions:

```text
authority
execution
response_integrity
causal_validity
```

The adapter derives only continuation posture. It does not issue authorization,
observe execution, verify claims, or decide causal truth.

### Allowed continuation modes

```text
CONTINUE_SIDE_EFFECT
RETRY_SIDE_EFFECT
REPORT_ONLY
REMEDIATE_RESPONSE
REVALIDATE
BLOCKED
ALREADY_CONSUMED
```

A committed or already observed side effect cannot be replayed after restart.
An errored operation may be retried only when the stored retry profile permits
it and the exact idempotency key is supplied. Evidence or context drift requires
a new snapshot.

Historical snapshots remain reportable even after expiry or evidence drift, but
they cannot silently regain live permission.

### Snapshot chain rules

`assessSnapshotChain()` rejects:

- broken `previous_ref` links;
- transition, subject, action, or binding substitution;
- removed observation evidence;
- committed-side-effect rollback;
- executed-to-unobserved rollback;
- terminal authority reopened without a new explicit authorization epoch;
- capture-time rollback.

A new authorization epoch must use a different `authorization_ref` and set
`reauthorization_ref` to that exact reference.

## Included regression tests

- one-byte object tampering is detected;
- an executed side effect consumes the decision;
- pending approval survives restart/replay;
- context drift requires revalidation;
- a corrupted projection fails closed against replay;
- active unobserved work may continue after restart;
- committed side effects cannot replay;
- expired snapshots cannot resume side effects;
- exact idempotent retry is distinguished from unsafe retry;
- failed response integrity routes to remediation only;
- invalid causal lineage blocks continuation;
- evidence drift requires a rebuilt snapshot;
- stale snapshots remain historical-report-only;
- cross-subject substitution fails;
- terminal snapshot state cannot be rolled back to a permissive state.

## Boundary

The continuity adapter proves deterministic persistence and resume-policy
evaluation over supplied record references and dimensions. It does not prove the
underlying authority provider, observation source, integrity verifier, or causal
auditor is correct.

## Next version

v0.2 should add:

- Ed25519 signatures;
- verifier identity and key rotation;
- signed checkpoint manifests;
- explicit approval resolution objects;
- cross-runtime conformance vectors.
