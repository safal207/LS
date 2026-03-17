# CEL Audit & Economic Efficiency

## Цель
Документ фиксирует минимальный аудит- и аналитический контур для экономической эффективности Market/CEL слоя.

## Что реализовано

- Новый модуль `EconomicsAudit` (`python/modules/cel/economics_audit.py`) для расчета:
  - `GMV` (`gmv_ct`),
  - количества payout событий,
  - `median` и `p95` payout latency,
  - `dispute_rate`,
  - `rollback_rate`,
  - `verification_pass_rate`,
  - сводного `economic_efficiency_score`.

- Экспортировано в CEL package API (`python/modules/cel/__init__.py`).
- Добавлены unit-тесты (`python/tests/test_cel_economics_audit.py`).

## Формула эффективности

`economic_efficiency_score` рассчитывается как взвешенный агрегат:

- 50% — verification pass rate,
- 25% — (1 - dispute rate),
- 15% — (1 - rollback rate),
- 10% — latency-компонента `(1 - min(1, p95_latency/3600))`.

Итоговый score ограничен в диапазоне `[0,1]`.

## Практическое использование

1. Собрать append-only события рынка (proposal/task created, verification, payout, disputes, rollback).
2. Передать список событий в `EconomicsAudit().summarize(events)`.
3. Использовать `AuditMetrics` для:
   - dashboard,
   - release gate,
   - weekly economics review.

## Следующий шаг

- Подключить `EconomicsAudit` в операторский dashboard/API,
- хранить историю weekly snapshot,
- сравнивать delta `economic_efficiency_score` неделя-к-неделе.
