# Web4 Runtime Migration Guide

## Scope

This guide describes migration from RTT-specific call paths (`RttSession`) to the transport-agnostic path (`Web4Session` + `TransportBackend`).

It applies to:

- `python/modules/web4_runtime/rtt.py`
- `python/modules/web4_runtime/transport.py`
- `python/modules/web4_runtime/transport_registry.py`
- `python/modules/web4_runtime/web4_session.py`

## Compatibility baseline

- RTT-direct usage remains supported.
- New integrations should prefer `Web4Session`.
- Transport behavior must remain contract-compatible (`python/tests/test_web4_transport.py`).

## API mapping

| RTT-specific | Transport-agnostic |
| --- | --- |
| `RttSession.send(message, priority=...)` | `Web4Session.send(message, priority=...)` |
| `RttSession.receive()` | `Web4Session.receive()` |
| `RttSession.pending` | `Web4Session.pending()` |
| `RttSession.stats` | `Web4Session.stats()` |
| `RttSession.heartbeat()` | `Web4Session.heartbeat()` |
| `RttSession.check_heartbeat_timeout()` | `Web4Session.check_heartbeat_timeout()` |

## Migration steps

1. Wrap existing RTT sessions with `RttTransport`.
2. Replace direct `RttSession` calls in application code with `Web4Session`.
3. Move transport construction into `TransportRegistry` factories.
4. Keep RTT lifecycle hooks (`register_on_session_open/close/...`) only where explicitly required.
5. Validate observability payloads include `transport_type` across all used backends.

## Before/after example

Before:

```python
from modules.web4_runtime.rtt import RttConfig, RttSession

session = RttSession[str](config=RttConfig(max_queue=16))
session.send("m1")
item = session.receive()
pending = session.pending
```

After:

```python
from modules.web4_runtime.rtt import RttConfig, RttSession
from modules.web4_runtime.transport import RttTransport
from modules.web4_runtime.web4_session import Web4Session

rtt = RttSession[str](config=RttConfig(max_queue=16))
session = Web4Session[str](transport=RttTransport(rtt))
session.send("m1")
item = session.receive()
pending = session.pending()
```

## Rollout strategy

1. Add transport-agnostic wrappers first, keep existing RTT logic untouched.
2. Switch one integration surface at a time (CLI, worker, service endpoint).
3. Run contract tests after each surface migration.
4. Remove RTT-direct wiring only after parity checks and production soak pass.

## Acceptance criteria

- No regressions in `python/tests/test_web4_transport.py`.
- Runtime invariants stay green (`test_global_flow.py`, `test_async_rtt.py`, `test_web4_runtime.py`).
- Observability events preserve `transport_type`.
- Existing RTT-only hooks still function where required.
