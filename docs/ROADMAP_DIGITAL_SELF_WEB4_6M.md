# Roadmap: Digital Self + Web4 (GhostGPT / LS)

Документ задаёт практический план на **3–6 месяцев** с приоритетами:
1) сначала self-ядро и обучение,
2) затем протоколы и безопасность,
3) затем value/merit-метрики,
4) далее масштабирование Web4,
5) и только после этого монетизация.

## Общая стратегия

- **Сначала строим self + внутреннее обучение.**
- **Потом подключаем сеть и протоколы обмена знаниями.**
- **Далее оцениваем и награждаем лучших участников.**
- **В конце масштабируем и монетизируем через Web4.**

---

## Фаза 1 (1–2 месяц): Центр ориентации и самосборки

**Цель:** создать единую карту self, где агент объединяет память, причинность и траектории опыта.

### 1.1 Self-State Aggregation
- Собрать `STM + LTM + CausalMemory + TemporalGraph` в единый snapshot центра ориентации.
- Сохранять `MissionState`, `adaptive_bias`, ключевые cognitive markers в persistent storage.
- Добавить визуальные срезы self:
  - trajectory history;
  - resonance map;
  - action log.

### 1.2 Internal Feedback Loop
- Подключить reflection/reasoning + metabolism для непрерывного learning loop.
- Автоматически корректировать `MissionState` и когнитивные приоритеты по outcomes.

### Definition of Done
- Snapshot self-state восстанавливается без потери критичных causal/temporal связей.
- После серии интеракций наблюдается детерминированное обновление минимум 2 адаптивных параметров.

---

## Фаза 2 (2–3 месяц): Протоколы взаимодействия и безопасность

**Цель:** агенты безопасно обмениваются знаниями между собой и с человеком.

### 2.1 Human-Agent Protocol (HCP)
- Ввести проверку согласия и эмоциональной безопасности.
- Поддержать `HCP_CONTEXT` и `HCP_DECISION` для объяснимости действий.

### 2.2 Agent-Agent Protocol (CIP)
- Реализовать path для `FACT_PROPOSE`, `FACT_CHALLENGE`, `FACT_CONFIRM`.
- Подключить Trust FSM + Anti-Hallucination Policy.
- Провести sync-тесты обмена между агентами.

### 2.3 Value / Merit Ledger Foundations
- Подготовить основу учёта вклада агента.
- Ввести метрику ценности через `resonance` / `harmony_bonus`.

### Definition of Done
- HCP/CIP проходят e2e-сценарий с логируемыми safety/consent решениями.
- Trust-state и факт-потоки реплеятся из event-log.

---

## Фаза 3 (3–4 месяц): Метрики и Proof-of-Value

**Цель:** формализовать оценку ценности идей и запустить royalty/value контур.

### 3.1 Resonance & Harmony
- Зафиксировать thresholds для отбора «лучших идей».
- Формализовать бонусы за синергию и согласованность с causal memory.

### 3.2 Merit Ledger
- Запустить децентрализованный учёт вкладов в пилотном режиме.
- Включить начисление `credit/value` для H→A и A→A взаимодействий.

### 3.3 Simulation & Stress Test
- Проверить распределение value при конфликтующих траекториях.
- Подключить внешних агентов и протестировать sync версий личности.

### Definition of Done
- Для lesson-веток есть trace: `proposed → validated → merged/rejected → reused → credited`.
- Метрики resonance/harmony влияют на decision policy воспроизводимо.

---

## Фаза 4 (4–6 месяц): Web4-сеть и масштабирование

**Цель:** масштабировать обмен знаниями и обучение в multi-agent среде.

### 4.1 External Agent Integration
- Подключить сторонних (в т.ч. платных) агентов через policy-gated onboarding.
- Валидировать внешний knowledge flow через CIP + Trust FSM.

### 4.2 Secure & Signed Knowledge Exchange
- Ввести Ed25519 подписи и canonical JSON для межагентных сообщений.
- Добавить replay-protection и версионирование state/self snapshot.

### 4.3 Continuous Learning & Scaling
- Непрерывное обучение агента на network outcomes.
- Тестировать устойчивость к конфликтующим/шумным знаниям.

### Definition of Done
- Межагентный обмен подписан и проверяем cryptographically.
- Система удерживает стабильность на soak/chaos сценариях без деградации policy quality.

---

## Фаза 5 (6 месяц+): Монетизация и роялти-поток

**Цель:** конвертировать ценность идей в доступ к ресурсам/экономические механики.

### 5.1 Credit → Resource Conversion
- Проработать контур конверсии `experience_credit` в доступ к ресурсам/токенам.
- Проверить совместимость с Merit Ledger и governance правилами.

### 5.2 Proof-of-Value Market
- Запустить ограниченный pilot-market идей.
- Валидировать reward-механику на закрытой сети агентов.

### Definition of Done
- Есть прозрачная формула value accrual и audit trail по начислениям.
- Экономический контур не ломает safety/quality приоритеты cognitive ядра.

---

## Приоритеты реализации (execution order)

`Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5`

Release-gates:
1. **Gate A (после Phase 1):** self snapshot/restore + adaptive feedback работает стабильно.
2. **Gate B (после Phase 2):** HCP/CIP + Trust FSM проходят интеграционные сценарии.
3. **Gate C (после Phase 3):** Proof-of-Value и merit-credit начисляются детерминированно.
4. **Gate D (после Phase 4):** secure signed exchange и multi-agent scaling подтверждены.
