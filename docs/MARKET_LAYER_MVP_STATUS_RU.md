# Market Layer MVP — итоговый статус (100%)

## Итог

План MVP закрыт полностью, включая шаги, которые выводят систему из «просто API» в исполняемый экономический протокол:

`capital -> task -> execution -> verification -> payout -> reputation -> feedback`

## Что закрыто

1. **Capital / Treasury layer**
   - проекты с treasury,
   - reserve reward при создании задачи,
   - блокировка задач при недостатке средств.

2. **Task + Bid market**
   - ставки,
   - ручное назначение,
   - auto-assign (`assign/best`) по governance scoring.

3. **Execution layer (реальный runtime)**
   - `execute_task` endpoint,
   - `autoloop` endpoint,
   - LLM-вызов (при наличии ключа) + fallback.

4. **Verification v2**
   - стадии `auto`, `reviewer`, `impact`,
   - автоматический перевод в `verified/disputed` по результатам стадий.

5. **Settlement + holdback scheduler**
   - immediate payout + delayed holdback,
   - `settlements` таблица,
   - `POST /settlement/run` для релиза.

6. **Reputation + penalties**
   - апдейт по quality,
   - штраф за спор через `rollback_penalty`.

7. **Governance surface**
   - runtime-настройка коэффициентов и holdback-параметров через API.

8. **Ledger / Observability**
   - append-only события для капитала, исполнения, верификации, выплат и governance.

## Реальный use-case

Добавлен end-to-end сценарий **Landing Generator**:

- задача с `use_case=landing_generator`,
- execution генерирует HTML+CTA артефакт,
- staged verification валидирует результат,
- settlement закрывает цикл выплат.

## Что дальше (уже Phase 2, не MVP)

1. RBAC и роли reviewer/governance.
2. Фоновый worker вместо ручного `/settlement/run`.
3. KPI dashboard и cohort-аналитика.
4. Multi-tenant / auth / billing.
