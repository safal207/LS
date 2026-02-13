# Web4 Runtime QoS & Backpressure Policies

Web4 RTT queue now supports four overflow strategies configured via `RttConfig.backpressure_policy`:

- `error` — fail fast with `BackpressureError` when queue is full.
- `dropoldest` — evict oldest queued message and accept the new one.
- `dropnewest` — keep queued messages, discard the incoming message.
- `block` — wait for free slot up to `RttConfig.block_timeout_s`, then fail with timeout.


## Block policy guarantees

- Spurious wakeups are handled via predicate-based waiting (`wait_for`).
- Disconnect during wait aborts immediately with `DisconnectedError`.
- Multiple concurrent senders wait independently.
- No fairness guarantee between waiting senders.
- Queue availability is rechecked atomically after wakeup.

## Stats (`RttStats`)

`RttSession.stats` exposes queue behavior counters:

- `attempted`: total send attempts.
- `enqueued`: messages accepted into queue.
- `dropped_oldest`: number of evictions under `dropoldest`.
- `dropped_newest`: number of discarded new messages under `dropnewest`.
- `dropped`: derived total dropped count.
- `blocked`: number of block-policy overflow entries.
- `errors`: number of failed sends (disconnect, timeout, error policy).
- `overflow_events`: number of times send hit full queue.
- `max_queue_len`: peak queue depth observed.

## Python example

```python
from modules.web4_runtime.rtt import RttConfig, RttSession

session = RttSession[str](
    config=RttConfig(
        max_queue=2,
        backpressure_policy="dropoldest",
    )
)

session.send("m1")
session.send("m2")
session.send("m3")  # m1 evicted

print(session.receive())  # m2
print(session.stats)
```
