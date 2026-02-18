# Issue Draft: Full Load Test Cycle for Global Flow + RTT Runtime

## Objective
Run full local validation and stress cycle for `GlobalFlowController` + RTT runtime, then promote stable checks into CI-safe coverage.

## Reference
- Detailed plan: `docs/LOAD_TEST_PLAN.md`

## Required Sequence
- [ ] Phase 1: Baseline correctness gate
- [ ] Phase 2: Local stress sanity
- [ ] Phase 3: Chaos validation
- [ ] Phase 4: Soak test
- [ ] Phase 5: Promote CI-friendly subset
- [ ] Phase 6: Final validation and sign-off

## Acceptance Criteria
- [ ] `total_pending` invariants hold in all phases
- [ ] sync/async global unblock behavior verified
- [ ] no event-loop blocking on sync locks
- [ ] no notify-task leaks
- [ ] no starvation/deadlocks under stress
- [ ] CI subset is deterministic and fast

## Suggested Evidence To Attach
- phase-by-phase pass/fail logs
- wakeup latency p50/p95/p99
- max queue depth / max pending
- soak stability metrics (memory/task growth)
