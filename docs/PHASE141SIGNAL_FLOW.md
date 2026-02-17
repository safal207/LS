# Phase 14.1 Signal Flow

## Tick flow

1. `MultiAgentSystem.step_all()` вычисляет `execution_order` через `GlobalTickCoordinator`.
2. Все агенты выполняются в этом порядке.
3. После завершения всех агентов собираются локальные сигналы через `broadcast_signals()`.
4. Дополнительные коллективные сигналы (`collectivesocialshift`, `collectivecooperation`, `collectivesocialconflict`) добавляются в deterministic очередь.
5. В конце тика вызывается `collective_signal_bus.process_tick()`:
   - fast-path: при пустой очереди `process_tick()` завершаетcя мгновенно;
   - под lock снимается batch из pending-очереди через `itertools.islice()`;
   - batch обрабатывается без lock;
   - под lock обновляются метрики (`total_processed`, `queue_size`, `tickswithdropped_signals`, `avgbatchsize`, `queuepeakper_tick`).

## Determinism guarantees

- FIFO за счёт deque и последовательного batch draining.
- Барьер доставки: сигналы не доставляются в середине агентного цикла.
- Reentrancy-safe: повторные `emit()` во время обработки попадают в следующий тик.

## Monitoring

- `queue_size`: текущий хвост pending-очереди после enqueue/process.
- `tickswithdropped_signals`: количество тиков, где были drop из-за `max_queue_size`.
- `avgbatchsize`: средний размер фактически обработанных батчей (взвешенно по `total_processed`).
- `queuepeakper_tick`: пиковое наблюдаемое значение длины pending-очереди на старте тика.
- Логи перегрузки:
  - warning: >90%
  - critical: >98%
