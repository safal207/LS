# Market Layer MVP — позиционирование, итоги и следующие шаги

## 1) Позиционирование

**Что это:**

`market_layer_mvp` — это минимальный исполняемый слой агентной экономики для цикла:

`task -> bid/assign -> artifact -> verification -> settlement -> reputation -> ledger`

**Что это НЕ является:**

- не production-grade биржа,
- не финальная token/treasury-экономика,
- не полный governance-протокол.

Это **MVP-инфраструктура**, которая доказывает работоспособность экономического контура и даёт базу для итераций.

---

## 2) Что уже сделано (закрыто)

### API и сценарии

Закрыт рабочий API-контур:

- `POST /agents`, `GET /agents`
- `POST /tasks`, `GET /tasks`
- `POST /tasks/{id}/bids`, `GET /tasks/{id}/bids`
- `POST /tasks/{id}/assign`
- `POST /tasks/{id}/deliver`
- `POST /tasks/{id}/verify`
- `POST /tasks/{id}/dispute`
- `POST /tasks/{id}/accept`
- `GET /ledger`

### Экономические механики

- escrow lock на старте задачи,
- settlement с holdback (20%),
- репутация агента от качества артефакта,
- append-only ledger событий,
- ставки и выбор исполнителя (bid + assign),
- ветка dispute.

### Инженерная база

- FastAPI + SQLAlchemy + SQLite,
- smoke/e2e тесты жизненного цикла,
- документация запуска и flow-схема.

---

## 3) Степень готовности

Для цели MVP (доказать экономический цикл в работающем сервисе) — **готово**.

Практически это означает:

1. можно создавать рынок задач,
2. можно принимать конкурентные ставки,
3. можно проводить верификацию и спор,
4. можно выполнять выплаты с holdback,
5. можно наблюдать все ключевые события через ledger.

---

## 4) Что сознательно оставлено за рамками MVP

- scheduled release для `T+7/T+30`,
- peer-review роли и multi-step verification,
- риск-скоринг и приоритизация задач,
- treasury per project + бюджетные лимиты,
- SLA/дедлайны и штрафные функции.

Это не пробелы реализации, а **следующая итерация** после стабилизации базового MVP.

---

## 5) План следующих шагов (после закрытия MVP)

## Шаг 1 — Settlement Scheduler

Добавить таблицу отложенных выплат и фоновый воркер:

- `settlements(id, task_id, amount, release_at, status)`
- endpoint `POST /settlement/run`
- cron/worker для релиза `T+7 / T+30`

**Результат:** holdback превращается в реальную отложенную выплату.

## Шаг 2 — Verification v2

Разделить проверку на стадии:

- auto-check,
- reviewer-check,
- optional impact-check.

**Результат:** меньше ложных acceptance и прозрачный dispute workflow.

## Шаг 3 — Auction Scoring

Добавить выбор победителя по скору:

`score = w_price * price + w_rep * reputation + w_speed * speed`

**Результат:** назначение исполнителя не только вручную, но и по модели качества.

## Шаг 4 — Treasury Layer

Ввести `project_treasury` и budget allocation:

- лимиты по проектам,
- запрет публикации задач без покрытия,
- отчёты по spend/remaining.

**Результат:** экономический контур становится финансово управляемым.

## Шаг 5 — Governance Surface

Добавить управляемые параметры:

- `holdback_rate`,
- веса auction scoring,
- штрафы за rollback/dispute.

**Результат:** можно эволюционировать экономику без изменения кода.

---

## 6) Рекомендуемое решение сейчас

Текущий MVP можно **официально считать завершённым** и перейти к Шагу 1 (Settlement Scheduler) как к следующему этапу плана.
