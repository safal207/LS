# Phase 14.5 Metrics Specification

## Новые метрики

### Regulator Metrics
- `regulator_volatility`: скользящее стандартное отклонение throughput_factor (окно 100 тиков)
- `regulator_alpha_current`: текущее значение alpha
- `regulator_adjustment_velocity`: скорость изменений параметров/тик

### Transport Metrics
- `transport_failover_count`: количество переключений на backup
- `transport_error_rate`: ошибки/тик по всем транспортам
- `transport_latency_p99`: 99-й перцентиль latency

### Priority Queue Metrics
- `priority_queue_depth`: глубина очереди по приоритетам
- `priority_inversion_count`: случаи обработки низкого приоритета перед высоким
- `priority_wait_time_avg`: среднее время ожидания по приоритетам

## Alerting Thresholds

| Метрика | Warning | Critical |
|---------|---------|----------|
| `regulator_volatility` | > 0.5 | > 0.8 |
| `transport_failover_count` | > 5/hour | > 20/hour |
| `priority_queue_backlog` | > 100 | > 500 |
| `transport_error_rate` | > 0.01 | > 0.05 |
