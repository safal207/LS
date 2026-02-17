# Phase 14.6 Performance Optimizations

## Priority Queue O(log n)

Ранее: O(n) вставка через `deque.insert()`.
Теперь: O(log n) вставка через `heapq`/`BinaryHeap`.

## Incremental Volatility (Welford's Algorithm)

Ранее: O(n) пересчёт на каждом шаге.
Теперь: O(1) инкрементальное обновление (`count`, `mean`, `m2`).

## Failover Recovery

Добавлен автоматический возврат к primary транспорту после заданного числа успешных операций на backup.

## Production Metrics

Добавлены метрики:

- `failover_recovery_time_sec`
- `priority_queue_wait_time_p99_ms`
- `volatility_computation_time_ns`
- `adaptive_alpha_changes`
