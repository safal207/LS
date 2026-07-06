# Durable approval v0.1 conformance matrix

| Case | Authority | Requester | Presentation | Execution |
|---|---|---|---|---|
| agent cancels requester | `PENDING` | `CANCELLED` | `VISIBLE` | `UNUSED` |
| transport disconnects | `PENDING` | `ATTACHED` | `DISCONNECTED` | `UNUSED` |
| wait window elapses without expiry policy | `PENDING` | `ATTACHED` | `VISIBLE` | `UNUSED` |
| user explicitly rejects | `REJECTED` | `ATTACHED` | `VISIBLE` | `UNUSED` |
| approved claim survives restart without effect evidence | `APPROVED` | `ATTACHED` | `VISIBLE` | `IN_DOUBT` |

The matrix is reconstructed from append-only events by the reference reducer. It is not manually trusted runtime state.
