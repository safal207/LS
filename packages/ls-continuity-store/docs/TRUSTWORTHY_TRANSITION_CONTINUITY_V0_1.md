# LS Trustworthy-Transition Continuity Profile v0.1

**Status:** Draft stacked profile  
**Tracking issue:** [LS #768](https://github.com/safal207/LS/issues/768)  
**Base store:** [LS PR #766](https://github.com/safal207/LS/pull/766)  
**Canonical transition profile:** [Liminal #108](https://github.com/safal207/Liminal/issues/108)

## Purpose

This profile persists the exact evidence boundary required to decide whether an
interrupted trustworthy transition may continue after pause, restart, retry, or
runtime-context change.

It consumes independently issued records from authority, observation,
response-integrity, and causal-lineage components. LS does not replace those
components. It stores their references and derives continuation posture from the
supplied dimensions.

## Snapshot envelope

A snapshot is stored as an immutable LS `verification_receipt` envelope:

```text
schema = ls.continuity.v1
object_type = verification_receipt
previous_ref = prior snapshot object_id or null
payload.profile = org.ls.trustworthy-transition-continuity.v0.1
```

The payload binds:

```text
transition_id
subject_id
action_identity_digest
binding_digest
authorization_ref
observation_refs
response_integrity_ref
causal_audit_ref
evidence_set_digest
context_digest
authority_expires_at
side_effect_committed
retry profile
```

All non-null record and digest references use `sha256:<64 lowercase hex>`.

## Independent dimensions

```text
authority
execution
response_integrity
causal_validity
```

These dimensions remain independent. In particular:

- a truthful response does not create authority;
- valid causal lineage does not prove execution success;
- observed execution does not make a false response true;
- historical evidence does not create retry eligibility.

## Evidence-set digest

The evidence-set digest is computed over a canonical object containing:

```text
profile id
transition id
subject id
action identity digest
binding digest
sorted unique record references
```

Changing any referenced authority, observation, response-integrity, or causal
audit record changes the digest and requires a rebuilt snapshot.

## Resume operations

### `resume_side_effect`

Allowed only when:

- the selected snapshot is the latest stored snapshot for the transition;
- the complete stored `previous_ref` sequence is forward-only and valid;
- transition, subject, action, and binding match exactly;
- evidence and runtime context have not drifted;
- authority is `VALID` and not expired;
- causal validity is `VALID`;
- execution is `NOT_OBSERVED`;
- no side effect was committed;
- response integrity does not require remediation or revalidation.

### `retry_side_effect`

Allowed only after `OBSERVED_ERRORED` when the snapshot explicitly records
`retryable_after_error=true` and the request supplies the exact stored
idempotency key. A later snapshot cannot make retry eligibility permissive, or
replace its accepted key, unless that snapshot also adds fresh observation
evidence or starts an explicit authorization epoch.

### `report_only`

Historical reporting remains allowed after authority expiry, committed
execution, evidence drift, or context drift. The result lists drift checks but
does not reopen live permission.

### `remediate_response`

May continue a non-executing response-remediation workflow when response
integrity is `FAILED` or `PARTIAL`. This posture is not permission to repeat the
original side effect.

## Monotonic snapshot chain

Live resume evaluation reconstructs the transition's snapshot sequence from the
local event log. `assessSnapshotChain(previous, current)` and
`assessSnapshotSequence(snapshots)` reject:

- incorrect `previous_ref`;
- transition or subject substitution;
- action or binding substitution;
- removed observation references;
- `side_effect_committed: true -> false`;
- `OBSERVED_EXECUTED -> NOT_OBSERVED`;
- retry eligibility made permissive without fresh observation evidence or a new
  authorization epoch;
- capture-time rollback;
- terminal authority reopened under the same authorization reference.

Terminal authority remains sticky across intermediate states. A chain such as
`DENIED -> PENDING -> VALID` cannot hide the denied epoch.

Reopening a terminal authority state requires:

```text
current.authorization_ref != previous.authorization_ref
current.reauthorization_ref == current.authorization_ref
```

The older observations remain in the evidence set; a new authorization epoch
does not erase history.

An authorization epoch may be established while execution remains
`OBSERVED_BLOCKED`; sequence validation remembers that epoch only long enough to
clear that blocked state. A later blocked observation requires another new
epoch. If response recovery becomes unknown and later returns to `FAILED` or
`PARTIAL`, response remediation remains available without granting permission
to repeat the original side effect.

## Deterministic fixtures

The fixture suite covers:

1. active unobserved work resumed after restart;
2. committed execution rejected as replay;
3. expired snapshot rejected for live continuation;
4. exact idempotent retry after non-committing error;
5. wrong retry key requiring revalidation;
6. failed response routed to remediation only;
7. invalid causal lineage blocking continuation;
8. evidence drift requiring a new snapshot;
9. stale executed snapshot remaining reportable;
10. cross-subject substitution rejection;
11. terminal-state rollback rejection;
12. explicit reauthorization epoch acceptance.
13. content-addressed snapshot tampering rejection after restart.

Every primary fixture is persisted to SQLite/WAL, the database is closed,
reopened, and the immutable snapshot is loaded before evaluation. The tampering
fixture mutates a stored dimension byte and proves that reload fails closed on
the object hash before any resume decision is made.

## Package gate

The `LS Continuity Store` workflow is owned by the base store branch and runs:

```bash
npm install --no-audit --no-fund
npm run build
npm test
npm run demo
npm run demo:transition
```

The base demo creates its SQLite data directory explicitly before opening the
database. This makes the gate reproducible on a clean runner rather than relying
on an untracked local directory.

## Boundary

This profile proves deterministic persistence, evidence-set binding, restart
recovery, and continuation-policy evaluation over supplied records. It does not
prove:

- authority-provider correctness;
- observation-source integrity;
- response-claim truth;
- causal-audit correctness;
- signer identity;
- production safety or compliance.

## Canonical invariant

> A snapshot can preserve what was known. It cannot silently turn historical
> evidence into current permission.
