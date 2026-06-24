# Commit-Before-Effect Gate v0.1

Status: **local deterministic LS reference contract**  
Implementation issue: [#687](https://github.com/safal207/LS/issues/687)  
Parent: [#596](https://github.com/safal207/LS/issues/596)

## Purpose

This is the first LS boundary where a verified request may become an actual side effect.

```text
verified portable authorization bundle
  -> Gate
  -> Incubate
  -> Commit
  -> Execute
  -> execution record and effect receipt
```

Its central invariant is:

```text
no effect before durable commit
```

## Inputs

The gate consumes:

- an offline-verified authorization bundle;
- its stable verifier-result reference;
- bundle, authorization, task, trail, policy, scope, expiry, and nonce bindings;
- a protected action with stable action and idempotency identities;
- exact action reference, candidate digest, scope, payload, maturity, and expiry;
- current time and host-supplied precondition status.

The input bundle must have:

```json
{
  "valid": true,
  "commit_before_effect_eligible": true,
  "execution_authorized": false
}
```

Upstream execution authority is rejected. The right to invoke one effect is created only by a successfully persisted `COMMITTED` record.

## Canonical lifecycle

```text
RECEIVED
  -> VALIDATING
  -> HELD | REJECTED | EXPIRED | ACCEPTED
  -> COMMITTED
  -> EXECUTED
```

Pre-effect terminal states are:

- `HELD` — preconditions or maturity are not yet satisfied;
- `REJECTED` — authorization, binding, policy, scope, state, or journal checks failed;
- `EXPIRED` — the action or bundle is outside its validity window.

These states always keep:

```json
{
  "effect_attempted": false,
  "execution_authorized": false
}
```

## Durable commit

The reference journal writes a complete JSON execution record to a temporary file, flushes it, calls `fsync`, and atomically replaces the journal path.

The executor performs a mandatory read-back check:

```text
journal.load(execution_id).state == COMMITTED
```

If the `COMMITTED` write fails, the controller records `REJECTED` with `COMMIT_WRITE_ERROR`; the executor is not called.

## Harmless reference effect

The MVP effect writes one review-result JSON file using exclusive-create semantics.

The effect is:

- local;
- inspectable;
- deterministic;
- idempotent for the execution identity;
- bound to the protected action digest.

The reference contract explicitly excludes payments, deployments, repository merges, destructive calls, credentials, and arbitrary production APIs.

## Idempotency identity

The execution identity is derived from:

- authorization reference;
- action idempotency key.

The execution record separately stores the full action digest. Reusing the identity with different action bytes fails as a state conflict rather than producing a new effect.

A retry after `EXECUTED` returns the prior receipt and does not invoke the executor again.

## Recovery

### Interruption after commit, before effect

The journal contains `COMMITTED` and no effect file exists. Recovery reads the record and performs exactly one effect.

### Interruption after effect, before receipt persistence

The journal still contains `COMMITTED`, but the effect file already exists. Recovery inspects the file, verifies its action digest, and records `EXECUTED` without invoking the executor a second time.

## Execution authority

Earlier layers deliberately emitted `execution_authorized: false`.

At this boundary:

- `COMMITTED` means one bound effect invocation is authorized;
- `EXECUTED` means that permit has been consumed and a receipt exists;
- no reusable or general-purpose execution authority is created;
- a retry may retrieve the prior receipt but may not create a second effect.

## Decision codes covered by v0.1

- `COMMIT_EXECUTED`
- `DEFER_PENDING_CONTEXT`
- `TTL_EXPIRED`
- `REJECT_POLICY`
- `COMMIT_WRITE_ERROR`
- `PRIOR_RECEIPT_REUSED`
- `RECOVERED_AFTER_COMMIT`
- `RECOVERED_EXISTING_EFFECT`

Additional fail-closed paths include invalid bundle verification, missing verifier reference, upstream authority claims, action/candidate/scope mismatch, incomplete protected actions, invalid time windows, and idempotency state conflicts.

## Conformance vectors

1. valid bundle and action execute after durable commit;
2. pending preconditions produce `HELD` and no effect;
3. expired action produces `EXPIRED` and no effect;
4. scope mismatch produces `REJECTED` and no effect;
5. journal write error produces no effect;
6. duplicate retry reuses the prior receipt;
7. interruption after commit recovers one effect;
8. interruption after effect inspects and does not duplicate.

## Production boundary

The reference implementation proves local ordering and deterministic recovery for one idempotent, inspectable file effect.

It does **not** claim universal exactly-once behavior for arbitrary distributed side effects. A production backend additionally needs:

- a transactional durable journal;
- transactional nonce consumption or compare-and-set;
- idempotency support at the external API boundary;
- worker ownership leases or fencing tokens;
- a recovery policy for effects that cannot be inspected after timeouts.

## Relationship to draft PR #621

Draft PR #621 contains valuable earlier CaPU design evidence but is a conflict-blocked 101-commit stack. This contract rebuilds only the execution-control boundary on modern `main` and consumes the portable bundle merged in PR #685.

## Conformance

Run:

```bash
python tools/validate_commit_before_effect_v0_1.py
```

The machine-readable report is written to:

```text
artifacts/commit-before-effect-v0.1-result.json
```
