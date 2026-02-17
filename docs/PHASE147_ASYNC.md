# Phase 14.7 Async Runtime Support

## Async RttSession

```python
from modules.web4_runtime.async_rtt import AsyncRttSession
from modules.web4_runtime.rtt import RttConfig

session = AsyncRttSession[str](config=RttConfig(max_queue=1024, enable_priority_queue=True))
await session.send_async("message", priority=5)
msg = await session.receive_async()
```

## Benefits

- ✅ Non-blocking I/O для high-concurrency сценариев
- ✅ Интеграция с `asyncio` event loop
- ✅ Обратная совместимость: sync API остаётся

## Migration

```python
# Sync:
session.send("msg")

# Async:
await session.send_async("msg")
```

## Additional capabilities

- Runtime policy updates через `set_backpressure_policy(...)`
- Async-friendly wait helper: `await session.wait_message(timeout_s=...)`
