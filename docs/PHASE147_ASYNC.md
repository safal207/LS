# Phase 14.7: Async RTT Runtime

This phase introduces `AsyncRttSession` in `python/modules/web4_runtime/async_rtt.py`.

## Goals
- Async-first send/receive API for Web4 RTT.
- Preserve semantics of sync backpressure modes (`error`, `dropoldest`, `dropnewest`, `block`).
- Keep compatibility with existing `RttConfig` / `RttStats`.

## API
- `send_async(message, priority=None)`
- `receive_async()`
- `wait_message(timeout_s=...)`
- `disconnect()` / `reconnect()`
- `heartbeat()` / `check_heartbeat_timeout()`

## Notes
- Uses `asyncio.Condition` (no busy-spin loops).
- Disconnect notifies waiters to unblock blocked producers/consumers.
