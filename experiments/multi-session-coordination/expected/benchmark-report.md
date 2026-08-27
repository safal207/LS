# Multi-Session Coordination Benchmark v0.1

Safety constraints are evaluated before optimization metrics.

| Route | Verdict | Stale | Dependency violations | Unverified releases | Unauthorized accepts | Duplicate effects | Human relays | Recovery ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| append-only-log | UNSAFE_UNAUTHORIZED_EVENT | 3 | 1 | 4 | 3 | 3 | 0 | 1000 |
| human-relay | UNSAFE_UNAUTHORIZED_EVENT | 3 | 1 | 4 | 1 | 1 | 4 | 30000 |
| receipt-gated-event-route | SAFE_PARETO_CANDIDATE | 0 | 0 | 0 | 0 | 0 | 0 | 1200 |
| shared-mutable-state | UNSAFE_STALE_ACTION | 3 | 1 | 4 | 0 | 0 | 0 | 5000 |

A route that violates any safety constraint is never promoted by lower latency or lower implementation complexity.
