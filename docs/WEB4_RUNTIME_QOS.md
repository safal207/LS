# Web4 Runtime QoS & Backpressure Policies

Compatibility alias: `docs/WEB4RUNTIMEQOS.md` (symlink for legacy links).

Web4 RTT queue supports overflow strategies configured by `RttConfig.backpressure_policy`:

- `error` — fail fast with `BackpressureError` when queue is full.
- `dropoldest` — evict oldest queued message and accept the new one.
- `dropnewest` — keep queued messages, drop incoming message.
- `block` — wait for free slot via `Condition.wait_for(...)` up to `RttConfig.block_timeout_s`.

## Block policy behavior

- Uses predicate-based `wait_for` (no busy spin in Python implementation).
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
