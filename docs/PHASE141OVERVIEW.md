# Phase 14.1 Overview — Deterministic Signal Integration & Performance

Phase 14.1 завершает стабилизацию глобального multi-agent цикла.

## Что добавлено

- `MultiAgentSystem` выполняет агентов строго в `coordinator.compute_execution_order(...)` без повторной подготовки порядка.
- `DeterministicSignalBus` используется как единственный bus для коллективных сигналов, а `process_tick()` вызывается как барьер в конце `step_all()`.
- `process_tick()` переведён на batch-процессинг: очередь снимается под одной блокировкой, обработка идёт вне lock.
- Добавлены runtime-метрики:
  - `queue_size`
  - `tickswithdropped_signals`
- Добавлены предупреждения:
  - warning при ~90% очереди
  - critical при ~98% очереди
- Добавлены alias-поля для API совместимости (`shared_goal_pressure`, `collective_meta_drift`, `idea_quality_score` и т.д.).

## Ожидаемый эффект

- Детерминированный FIFO-порядок доставки сигналов.
- Отсутствие reentrancy-проблем при массовом эмите.
- Меньше lock-contention под высокой нагрузкой.
- Упрощённая диагностика перегрузки signal queue.
