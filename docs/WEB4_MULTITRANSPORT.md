# Web4 Runtime Multi-Transport Abstraction

This document reflects current transport abstraction in:

- `python/modules/web4_runtime/transport.py`
- `python/modules/web4_runtime/transport_registry.py`
- `python/modules/web4_runtime/web4_session.py`

## Core components

- `TransportBackend` protocol with methods:
  - `connect`, `disconnect`, `send`, `receive`, `pending`, `stats`, `heartbeat`, `check_heartbeat_timeout`
- `RttTransport` adapter for `RttSession`
- `TransportRegistry` factory registry for backend selection
- `Web4Session` transport-agnostic facade that emits transport-level observability events

## Behavior notes

- Existing RTT-direct usage remains valid.
- New paths should prefer `Web4Session` + selected `TransportBackend`.
- `Web4Session` records transport events with `transport_type` payload.

## Example

```python
from modules.web4_runtime.rtt import RttSession
from modules.web4_runtime.transport import RttTransport
from modules.web4_runtime.transport_registry import TransportRegistry
from modules.web4_runtime.web4_session import Web4Session

registry = TransportRegistry[str]()
registry.register("rtt", lambda: RttTransport(RttSession[str]()))
transport = registry.create("rtt")
session = Web4Session[str](transport=transport)

session.send("hello")
print(session.receive())
```
