# Durable approval conformance matrix

## v0.1 — pending authority ownership

| Case | Authority | Requester | Presentation | Execution |
|---|---|---|---|---|
| agent cancels requester | `PENDING` | `CANCELLED` | `VISIBLE` | `UNUSED` |
| transport disconnects | `PENDING` | `ATTACHED` | `DISCONNECTED` | `UNUSED` |
| UI is dismissed without explicit rejection | `PENDING` | `ATTACHED` | `NOT_PRESENTED` | `UNUSED` |
| wait window elapses without expiry policy | `PENDING` | `ATTACHED` | `VISIBLE` | `UNUSED` |
| user explicitly rejects | `REJECTED` | `ATTACHED` | `VISIBLE` | `UNUSED` |
| approved claim survives restart without effect evidence | `APPROVED` | `ATTACHED` | `VISIBLE` | `IN_DOUBT` |

## v0.2 — terminal authority and reconciliation

| Case | Authority | Requester | Presentation | Execution | Required attribution |
|---|---|---|---|---|---|
| configured policy expiry | `EXPIRED` | `ATTACHED` | `VISIBLE` | `UNUSED` | matching policy actor + expiry evidence |
| verified context invalidation | `INVALIDATED` | `ATTACHED` | `VISIBLE` | `UNUSED` | verifier/runtime actor + drift evidence |
| durable state loss | `LOST` | `ATTACHED` | `VISIBLE` | `UNUSED` | runtime actor + integrity evidence |
| reconcile uncertain effect as committed | `APPROVED` | `ATTACHED` | `VISIBLE` | `COMMITTED` | effect verifier + observation evidence |
| reconcile uncertain effect as failed | `APPROVED` | `ATTACHED` | `VISIBLE` | `FAILED` | effect verifier + observation evidence |

The matrices are reconstructed from append-only events by the reference reducers. They are not manually trusted runtime state.

## Cross-version invariants

```text
requester lifecycle cannot manufacture authority resolution
presentation lifecycle cannot manufacture authority resolution
UI disappearance is not user rejection
LOST is not REJECTED
reconciliation does not mint new authority
single-use approval cannot be claimed twice
```
