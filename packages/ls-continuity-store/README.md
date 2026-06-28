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

## Included regression tests

- one-byte object tampering is detected;
- an executed side effect consumes the decision;
- pending approval survives restart/replay;
- context drift requires revalidation;
- a corrupted projection fails closed against replay.

## Next version

v0.2 should add:

- Ed25519 signatures;
- verifier identity and key rotation;
- signed checkpoint manifests;
- explicit approval resolution objects;
- cross-runtime conformance vectors.
