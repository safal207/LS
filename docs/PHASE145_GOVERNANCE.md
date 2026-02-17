# Phase 14.5 Advanced Governance

## Adaptive EMA Alpha

Регулятор теперь динамически настраивает `alpha` на основе волатильности нагрузки:

- `alpha=0.5` при высокой волатильности (быстрая адаптация)
- `alpha=0.2` при стабильной нагрузке (плавные изменения)
- `alpha=0.3` по умолчанию

## Cross-Transport Failover

`Web4Session` поддерживает автоматическое переключение на backup транспорт:

```python
registry = TransportRegistry[str]()
registry.register("rtt", lambda: RttTransport(RttSession[str]()))
registry.register("websocket", lambda: WebSocketTransport(...))

session = Web4Session[str](
    transport=registry.create("rtt"),
    backup_transport=registry.create("websocket"),
    failover_threshold=3,  # переключение после 3 ошибок
)
```

## Priority Queue

Сообщения могут иметь приоритет (0-10):

```python
session.send("critical", priority=10)  # обрабатывается первым
session.send("normal", priority=5)
session.send("background", priority=1)
```

## Enhanced Alerting

Новые пороги для алертов:

- `regulator_volatility > 0.5` → высокая волатильность
- `failover_count > 5/hour` → частые переключения транспортов
- `priority_queue_backlog > 100` → 积压 приоритетных сообщений
