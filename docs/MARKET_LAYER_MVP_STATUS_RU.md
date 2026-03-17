# Market Layer MVP — итоговый статус (100%)

## Текущее состояние

Все запланированные шаги из MVP-roadmap реализованы в коде и покрыты экспресс-тестами.

Базовый контур:

`task -> bid/assign -> artifact -> verification(v2) -> settlement -> reputation -> ledger`

Расширенный контур:

`governance -> auction scoring -> treasury constraints -> scheduled payouts`

---

## Что реализовано полностью

1. **Task + Bid Market**
   - создание задач,
   - подача ставок,
   - ручное и авто-назначение (`assign/best`) по scoring.

2. **Verification v2**
   - staged-проверка (`auto`, `reviewer`, `impact`),
   - переход в `verified` после обязательных стадий,
   - переход в `disputed` при провале обязательной стадии.

3. **Escrow + Settlement Scheduler**
   - escrow lock при создании задачи,
   - immediate payout + holdback при acceptance,
   - отложенные выплаты через `settlements` + `POST /settlement/run`.

4. **Reputation + Penalty**
   - обновление репутации по качеству артефакта,
   - штраф при dispute через governance-параметр `rollback_penalty`.

5. **Treasury Layer**
   - задачи публикуются только при достаточном балансе проекта,
   - reward резервируется из `project.treasury_balance`.

6. **Governance Surface**
   - параметры экономики через API:
     - `holdback_rate`
     - `holdback_days`
     - `auction_weight_price`
     - `auction_weight_rep`
     - `auction_weight_speed`
     - `rollback_penalty`

7. **Ledger / Observability**
   - append-only события по ключевым действиям:
     task, bid, verification, payout, settlement, treasury, governance.

---

## Практический вывод

MVP можно считать **завершённым на 100%** относительно текущего плана.

---

## Рекомендованные next-phase шаги (после MVP)

Если идти дальше, это уже не «доделка MVP», а **Phase 2**:

1. RBAC/roles для reviewer/governance.
2. Async worker (Celery/RQ) вместо ручного `/settlement/run`.
3. История версий governance параметров + approval workflow.
4. KPI/metrics dashboard (GMV, dispute rate, payout latency, acceptance quality).
5. Multi-project portfolio allocation policies.
