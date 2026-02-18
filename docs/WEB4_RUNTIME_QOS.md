# Web4 Runtime QoS & Backpressure Policies

Compatibility alias: `docs/WEB4RUNTIMEQOS.md` (symlink for legacy links).

Web4 RTT queue supports overflow strategies configured by `RttConfig.backpressure_policy`:

Sync (`RttSession`) and async (`AsyncRttSession`) both delegate queue mechanics to `modules.web4_runtime.rtt_queue.RttQueue` to keep ordering, overflow, and compaction behavior identical.

**Config invariant:** `RttConfig.max_queue` must be `>= 1`. Invalid values now raise `ValueError` (Python) / `PyValueError` (Rust binding) instead of being silently clamped.

- `error` — fail fast with `BackpressureError` when queue is full.
- `dropoldest` — evict oldest queued message and accept the new one.
- `dropnewest` — keep queued messages, drop incoming message.
- `block` — wait for free slot via condition wait up to `RttConfig.block_timeout_s`.

## Block policy behavior

- Uses blocking condition waits (no fixed 10ms polling loop).
- Handles spurious wakeups safely.
- Disconnect during blocking wait exits with `DisconnectedError`.
- Timeout exits with `BackpressureError("RTT backpressure: block timeout")`.
- Queue state is rechecked atomically after wakeup under condition lock.

## Stats (`RttStats`)

`RttSession.stats` exposes:

- `attempted`
- `enqueued`
- `accepted` (property alias to `enqueued`)
- `dropped_oldest`
- `dropped_newest`
- `dropped` (derived total)
- `blocked`
- `errors`
- `overflow_events`
- `max_queue_len`

## Python example

```python
from modules.web4_runtime.rtt import RttConfig, RttSession

session = RttSession[str](
    config=RttConfig(max_queue=2, backpressure_policy="dropoldest")
)

session.send("m1")
session.send("m2")
session.send("m3")  # evicts m1

print(session.receive())  # m2
print(session.stats.dropped_oldest)  # 1
```


## Admission order with `GlobalFlowController`

When `RttSession.flow_controller` is configured, admission is evaluated in this order:

1. Local queue bound (`RttConfig.max_queue`).
2. Global controller bound (`GlobalFlowController.total_limit` / per-session strategy).

This means global pressure can reject new messages even when a local session queue still has free slots.

## DropOldest With Global Flow

- Eviction is accounted as a real dequeue in `GlobalFlowController`.
- Replacement enqueue is admitted only after a successful `try_enqueue`.
- If global admission fails after eviction, the new message is dropped and local/global counters remain consistent.

## Global Waiter Wakeups

- Sync producers blocked by global limits wait on controller-level free-space signals.
- Async producers waiting on global pressure are woken by flow-controller free-space notifications.
- Dequeue/reset paths trigger these notifications so blocked senders can retry before timeout.

## Non-Weakref Session Ownership

- Sessions that cannot be weak-referenced are stored strongly by the flow controller.
- Call `unregister_session(session)` to release those strong references explicitly.
