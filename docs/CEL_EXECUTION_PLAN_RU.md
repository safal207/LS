# Web4 + CEL: Execution Plan (старт)

Этот документ фиксирует практический стартовый план внедрения Cognitive Economy Layer (CEL) после утверждения архитектурной схемы.

Связанный референс: `docs/WEB4_CEL_SCHEMA_RU.md`.

---

## Цель фазы

Запустить production-ready MVP рынка решений между агентами за 6–10 недель, с прозрачными экономическими событиями, атомарными расчётами и базовой репутационной петлёй.

---

## Scope MVP

1. CTL Event Schema v1
2. CEL Wallet + Transfer API
3. Decision Listing API
4. Outcome Settlement Worker
5. LTP-lite Reputation
6. Hardening (CEM reliability + observability)

---

## План по спринтам

## Sprint 1 (Недели 1–2): CTL Event Schema v1

### Deliverables
- JSON Schema/contract для:
  - `proposal_created`
  - `proposal_purchased`
  - `outcome_settled`
  - `price_changed`
- Поля: `event_id`, `trace_id`, `event_type`, `ts`, `producer`, `schema_version`, `signature`.
- Идемпотентность: дедупликация по `event_id` + окно повторной обработки.
- Версионирование: политика backward compatibility для `v1.x`.

### Definition of Done
- Схемы и примеры payload лежат в репозитории.
- Есть unit-проверки валидаторов схем.
- Любой producer/consumer проходит contract-check на CI.

### Риски
- Разные команды по-разному трактуют поля.

### Митигация
- Один canonical schema package + CI contract gate.

---

## Sprint 2 (Недели 2–3): CEL Wallet + Transfer API

### Deliverables
- Операции: `debit`, `credit`, `hold`, `release`, `settle`.
- Атомарные переводы `from_agent -> to_agent`.
- Wallet ledger + аудит трассы платежа (link to CTL event).

### Definition of Done
- Нет double-spend в конкурентных сценариях.
- API возвращает детерминированные коды ошибок.
- Финансовые события пишутся в CTL.

### Риски
- Гонки при высоком параллелизме.

### Митигация
- Транзакции/locks на уровне ledger + стресс-тесты конкурентности.

---

## Sprint 3 (Неделя 4): Decision Listing API

### Deliverables
- Endpoints: `create/list/get/buy/subscribe`.
- TTL и статус публикации (`active`, `expired`, `sold`, `archived`).
- Публикация маркет-сигналов в CEM (`proposal_created`, `proposal_sold`).

### Definition of Done
- Полный e2e: publish -> buy -> access grant.
- ACL/permission модель работает для buyer/seller.

### Риски
- Расхождение статуса между CEL и CEM.

### Митигация
- Outbox pattern + гарантированная публикация.

---

## Sprint 4 (Недели 5–6): Outcome Settlement Worker

### Deliverables
- Планировщик horizon-check (например, T+7).
- Расчёт outcome: hit/miss, error band, proxy PnL.
- Событие `outcome_settled` в CTL.

### Definition of Done
- Worker устойчив к повторам и рестартам.
- Settlement воспроизводим по trace_id и данным входа.

### Риски
- Некачественные входные market-data.

### Митигация
- Версионированные data sources + fallback провайдер.

---

## Sprint 5 (Недели 6–8): LTP-lite Reputation + Price Band

### Deliverables
- Расчёт `reputation_score` и `quality_score`.
- Выдача `suggested_price_band` для новых листингов.
- Событие `price_changed` в CEM.

### Definition of Done
- Метрика репутации пересчитывается автоматически по settlement-событиям.
- CEL применяет price band в новых публикациях.

### Риски
- Перекос цен из-за малого объёма истории.

### Митигация
- Минимальный порог наблюдений + Bayesian smoothing.

---

## Sprint 6 (Недели 8–10): Hardening и Go-Live

### Deliverables
- CEM reliability contract:
  - `at-least-once` delivery
  - exponential retry
  - dead-letter queue
  - backpressure policy
- Observability:
  - метрики: retry rate, consumer lag, settlement latency, failed transfers
  - алерты и SLO dashboard
- Runbook на инциденты (wallet mismatch, message backlog, delayed settlement).

### Definition of Done
- Нагрузочные тесты проходят целевые SLO.
- Есть on-call runbook и rollback-процедура.

### Риски
- Деградация под пиковым спросом.

### Митигация
- Throttling, priority queues, degrade mode.

---

## KPI на MVP

- p95 latency `buy_proposal` < 300ms
- Успешные settlements >= 99%
- Потери событий CEM = 0 (с учётом retry + DLQ)
- Доля idempotent replays без ошибок >= 99.9%
- Время пересчёта репутации после settlement < 5 минут

---

## Команда (минимум)

- 1 backend engineer (CEL/API)
- 1 backend engineer (ledger/CTL)
- 1 data/infra engineer (LTP/CEM/observability)
- 0.5 QA + 0.5 DevOps/SRE (shared)

---

## Стартовые артефакты на ближайшие 48 часов

1. RFC: `CTL Event Schema v1`
2. OpenAPI draft: `CEL Wallet + Transfer API`
3. Sequence test-case: `publish -> buy -> settle -> reprice`
4. Таблица рисков с владельцами и сроками митигации

После подготовки этих 4 артефактов можно официально стартовать Sprint 1.

---

## Sprint 1 — реализованные артефакты в репозитории

- Схема контракта: `schemas/ctl_event_v1.schema.json`
- Канонические примеры событий:
  - `schemas/examples/ctl_events/v1/proposal_created.json`
  - `schemas/examples/ctl_events/v1/proposal_purchased.json`
  - `schemas/examples/ctl_events/v1/outcome_settled.json`
  - `schemas/examples/ctl_events/v1/price_changed.json`
- Контракт-валидация (pytest + jsonschema): `python/tests/test_ctl_event_schema.py`


## Sprint 2 — реализованные артефакты в репозитории

- In-memory API кошелька и переводов: `python/modules/cel/wallet_api.py`
- Публичные экспорты модуля CEL: `python/modules/cel/__init__.py`
- Тесты Sprint 2 (атомарность, ошибки, аудит-событие): `python/tests/test_cel_wallet_api.py`
