# Phase 14.7 Global Flow Control

## Проблема

При 1000+ сессиях локальный backpressure каждой сессии не предотвращает перегрузку системы в целом.

## Решение: `GlobalFlowController`

```python
from modules.web4_runtime.flow import GlobalFlowController, BackpressureStrategy
from modules.web4_runtime.rtt import RttConfig, RttSession

controller = GlobalFlowController[str](
    max_total_pending=100_000,
    per_session_limit=10_000,
    strategy=BackpressureStrategy.PROPORTIONAL,
)

session = RttSession[str](
    config=RttConfig(max_queue=10_000, backpressure_policy="block"),
    flow_controller=controller,
)
```

## Стратегии backpressure

| Стратегия | Описание |
|-----------|----------|
| `proportional` | Распределяет квоты пропорционально активности сессии |
| `fair` | Round-robin распределение слотов |
| `priority` | Reserved extension point под priority-aware admission |

## Dynamic policy switching

```python
controller.set_strategy(BackpressureStrategy.FAIR)
controller.set_strategy(BackpressureStrategy.PRIORITY)
```
