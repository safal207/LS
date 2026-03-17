# Post-Web4 Roadmap: протоколы + экономика + продукт

## Контекст
После Web4 Mesh v0 следующий этап — перевести стек в production-поток:

1. **Протоколы**: CIP/HCP/LIP как исполняемые политики, а не только спецификации.
2. **Экономика**: HCP Marketplace + CEL как ежедневный рабочий контур.
3. **Операционка**: observability, CI, replay, KPI и безопасный rollout.

---

## Цели на 6 недель

### Цель A — Protocol Hardening (CIP/HCP/LIP)
- Ввести единый policy-layer для handshake/trust/consent/deferred acceptance.
- Обеспечить обязательную валидацию envelope и signature на runtime path.
- Добавить правила эскалации конфликтов и quarantine для спорных claims.

### Цель B — Marketplace Phase 2
- Довести RBAC (reviewer/governance/operator).
- Перевести settlement на фоновый worker по расписанию.
- Ввести KPI dashboard: fill-rate, payout latency, dispute rate, rollback rate.

### Цель C — Operator Surface
- Session replay для ключевых протокольных цепочек.
- Gate before promotion: стратегия не промотится без simulation + baseline check.
- Стандартизовать инцидентные runbooks для mesh/runtime/market.

---

## План по неделям

## Неделя 1 — Protocol policy-layer
- Реализовать policy hooks для:
  - CIP handshake + trust FSM checks,
  - HCP consent/clarity/pressure safety checks,
  - LIP deferred acceptance queue state transitions.
- Добавить contract-тесты на reject/defer/accept сценарии.

**DoD:** 90% критичных policy-сценариев покрыты unit/integration тестами.

## Неделя 2 — Envelope & signature enforcement
- Подключить canonical envelope validation в runtime router.
- Включить подписи и verify-fail fallback policy.
- Добавить compatibility tests для mixed peers (old/new envelope).

**DoD:** неподписанные или невалидные critical envelopes не проходят дальше policy gate.

## Неделя 3 — Marketplace RBAC + Governance controls
- Роли: `operator`, `reviewer`, `governance`, `executor`.
- Ограничить критичные actions по ролям (verify, penalty, governance params).
- Добавить audit trail на все privilege действия.

**DoD:** все sensitive endpoints защищены role checks + audit events.

## Неделя 4 — Settlement worker + reliability
- Перенести ручной settlement в periodic/background worker.
- Добавить retry strategy + DLQ + idempotency keys.
- Дать SLO метрики: success rate, latency, replay safety.

**DoD:** settlement автоматически закрывает очередь без ручного API триггера.

## Неделя 5 — KPI dashboard + replay
- Вынести KPI в операторский dashboard.
- Добавить event replay по цепочке:
  `publish -> buy -> settle -> reputation -> reprice`.
- Добавить фильтры по proposal/agent/time window.

**DoD:** оператор может воспроизвести любую критичную транзакцию из UI/API.

## Неделя 6 — Hardening & release gate
- Провести chaos/stress smoke на mesh+market связке.
- Зафиксировать release checklist и rollback plan.
- Включить mandatory simulation gate before strategy promotion.

**DoD:** есть формальный release gate и подтвержденный rollback сценарий.

---

## Протоколы: что именно делаем

## CIP
- Финализируем wire-level enforcement для `HELLO/FACT_* /STATE_UPDATE`.
- Проверяем replay-protection и trust transitions на каждом hop.

## HCP
- Применяем consent-first как обязательный runtime блокер.
- При `pressure>=80` или `clarity<=30` — авто-defer/slowdown policy.

## LIP
- Любой внешний claim сначала попадает в `pending/disputed`.
- В causal memory допускается только `accepted` после corroboration.

---

## KPI на выходе (обязательные)
- Protocol validation pass rate.
- Signature verification fail rate.
- Settlement completion latency p50/p95.
- Dispute rate / rollback rate.
- Replay success rate.
- Strategy promotion gate pass ratio.

---

## Риски и митигации
- **Риск:** рассинхрон policy между сервисами.
  - **Митигация:** единый policy package + contract tests в CI.
- **Риск:** рост latency из-за доп. валидации.
  - **Митигация:** отдельные fast-path checks + профилирование hot spots.
- **Риск:** ложные отклонения из-за строгих gate rules.
  - **Митигация:** staged rollout + feature flags + shadow mode.

---

## Команда и параллельность
- Поток 1 (Protocol): 1–2 backend engineers.
- Поток 2 (Market/CEL): 1–2 backend engineers.
- Поток 3 (Operator/Observability): 1 fullstack + 0.5 SRE/QA.

Потоки синхронизируются ежедневным 15-минутным protocol/market standup.
