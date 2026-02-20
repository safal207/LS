# Load Test Plan: Global Flow Controller + RTT Runtime

## Goal
Validate correctness and resilience of `GlobalFlowController` + RTT runtime in local stress conditions, then promote stable coverage into CI-safe tests.

## Reference Harness
- Runtime harness module: `python/modules/web4_runtime/loadtest.py`
- CLI entrypoint: `scripts/web4_runtime_load.py`
- Lightweight CI tests: `python/tests/test_web4_runtime_loadtest.py`
- Migration guide: `docs/WEB4_RUNTIME_MIGRATION_GUIDE.md`
- CI-safe checklist: `docs/WEB4_RUNTIME_CI_CHECKLIST.md`
- Extended load workflow: `.github/workflows/web4_runtime_extended_load.yml`

## Scope
- Sync RTT (`RttSession`)
- Async RTT (`AsyncRttSession`)
- Global admission (`GlobalFlowController`)
- Queue and backpressure semantics
- Wakeup behavior under contention

## Execution Order (Strict)
Run phases in order. Do not start next phase until current phase passes.

## Phase 1: Baseline Correctness (Pre-Load Gate)
### 1.1 Invariants
- `total_pending == sum(all session pending)`
- `total_pending <= total_limit`
- `session.pending <= max_queue`
- `dropoldest` keeps global accounting net-consistent
- sync and async wakeup contracts hold

### 1.2 Wakeup Contract
- Sync `block` sender wakes immediately on global slot free
- Async notify tasks execute and do not leak
- Cross-loop async usage raises `RuntimeError`
- Async event/condition lifecycle initializes once per loop

### 1.3 Deadlock Safety
- Async path does not block on `threading.RLock`
- Sync path does not stall event loop

### Phase 1 Exit Criteria
- All checks pass with no flakes in 3 repeated runs.
- Implemented baseline harness profile: `scripts/web4_runtime_load.py --phase phase1 --mode both`.

## Phase 2: Local Stress (Sanity Under Load)
### Scenario
- `10-50` sessions
- Each session sends `1k-5k` messages
- Random delay `0-5ms`
- Random priorities
- Random disconnect/reconnect

### Validate
- No deadlocks
- No blocked senders stuck past timeout contract
- No runaway queue growth
- Latency remains stable per configured thresholds

### Phase 2 Exit Criteria
- No invariant violations and no deadlocks across at least 3 runs.
- Implemented stress-sanity profile: `scripts/web4_runtime_load.py --phase phase2 --mode both`.

## Phase 3: Chaos Validation (Local)
### Chaos Inputs
- Random disconnect/reconnect
- Burst mode (e.g. 100 msgs in 1ms windows)
- Random block timeouts
- Random backpressure policies (`dropoldest`, `block`)
- GC pressure (`gc.collect()` loops)

### Validate
- No global accounting desync
- No lost wakeups
- No starvation
- `_notify_tasks` does not grow unbounded
- No cross-loop misuse regressions

### Phase 3 Exit Criteria
- Stable completion with no hangs and bounded memory/task growth.
- Implemented chaos profile: `scripts/web4_runtime_load.py --phase phase3 --mode both`.

## Phase 4: Soak Test (Long Run)
### Parameters
- Duration: `1-3h`
- `20-50` sessions
- Throughput target: `100-300 msg/s` aggregate
- Periodic reconnect + burst injections

### Validate
- No memory leak trend
- No monotonic growth in:
  - `_notify_tasks`
  - `_session_pending`
  - `_strong_sessions`
  - local queues
- Latency drift within tolerance

### Phase 4 Exit Criteria
- No degradation trends and no deadlocks through full soak window.
- Implemented soak profile: `scripts/web4_runtime_load.py --phase phase4 --mode both --soak-duration-s <seconds>`.

## Phase 5: Promote to Git (CI-Friendly)
### Keep in CI
- Invariants
- Sync/async wakeup contracts
- Cross-loop guard
- Notify task cleanup
- GC-race fallback invariants
- Lightweight fairness checks
- Load harness smoke checks (`python/tests/test_web4_runtime_loadtest.py`)

### Keep Out of CI
- Long soak tests
- Heavy chaos scenarios
- 10k+ message stress loops
- Aggressive GC pressure loops

### CI Requirement
- Tests finish quickly and deterministically.

## Phase 6: Final Validation
- Local stress + chaos + soak all stable
- CI-safe subset passes consistently
- No regressions in global flow admission semantics
- Runtime considered production-ready for current phase

## Suggested Test Matrix
- `sync_global_unblock_latency`
- `async_global_unblock_latency`
- `total_pending_consistency_under_gc_churn`
- `notify_task_execution_and_cleanup`
- `cross_loop_guard_enforced`
- `atomic_try_enqueue_under_contention`
- `reconnect_chaos_resilience`

## Reporting
For each phase capture:
- pass/fail
- duration
- max queue depth
- max pending
- wakeup latency p50/p95/p99
- notes on anomalies and fixes
