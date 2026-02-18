**Версия:** 0.1 (полный черновик)
**Дата:** 18 февраля 2026
**Автор:** Главный архитектор LS
**Статус:** Первый production-ready черновик. Готов к обсуждению и интеграции в Phase 22.

---

### 1. Назначение

Определить распределённый консенсус-протокол для **Global Merit Ledger**, который гарантирует:

- сильную eventual consistency Merit Score при геораспределённых узлах
- честный и проверяемый расчёт **NetworkEffectBonus** (главный механизм поощрения синергии)
- защиту от Sybil, fraud и partition-атак
- прозрачное и предсказуемое поощрение узлов, которые активно делятся данными (LoRA, beliefs, synthetic data)

Протокол специально спроектирован так, чтобы **самое выгодное поведение** в сети — активная синергия.

### 2. Threat Model

- Long-range partition (split-brain)
- Sybil + fake contributions
- Selective withholding данных (greedy nodes)
- Eclipse-атаки на high-Merit узлы
- Spam синергии (фейковые обмены)
- Replay-атаки на gossip

### 3. Design Principles (ключевые)

1. **Synergy-first** — узлы, которые активно обмениваются проверенными данными, получают приоритет в консенсусе и больший NetworkEffectBonus.
2. **Strong eventual consistency** — все узлы в конечном итоге соглашаются с одним и тем же состоянием ledger.
3. **Economic incentive alignment** — честная синергия всегда выгоднее эгоизма.
4. **Minimal trust** — протокол работает даже если 70 % узлов ведут себя честно.

### 4. Общая архитектура протокола

**Двухслойная модель:**

- **Layer 1 (Soft)** — Gossip (каждые 60 сек) — быстрый обмен deltas
- **Layer 2 (Strong)** — Periodic Merkle-root Broadcast (каждые 300 сек) — сильная фиксация состояния

### 5. Формальный протокол

#### 5.1 Gossip Layer

Каждый узел каждые 60 сек рассылает своему neighbour set (20–30 случайных узлов + 5 high-Merit):

```python
message = {
    "node_id": "...",
    "merit_delta": {...},           # изменения Merit
    "synergy_proofs": [list of signed exchanges],
    "timestamp": ts,
    "signature": sig
}
```

#### 5.2 Merkle-root Broadcast (Strong Layer)

Каждые 300 сек узлы с Merit ≥ 750 становятся **candidate validators**.
Из них выбирается **leader** по формуле:

```python
leader_score = merit * (1 + 2.0 * recent_synergy_ratio)
```

**recent_synergy_ratio** = (отданные + подтверждённые адаптеры) / (всего задач за последние 24 ч)

→ Узлы, которые активно участвуют в синергии, имеют **значительно выше шанс** стать leader и получить дополнительный NetworkEffectBonus.

#### 5.3 Conflict Resolution

При получении двух разных Merkle-roots:

1. Выбирается root с **наибольшим timestamp**.
2. При равенстве — root с **наибольшим суммарным Merit** подписавших узлов.
3. При равенстве — root с **наибольшим Synergy Score** (количество подтверждённых обменов внутри root).

### 6. NetworkEffectBonus — как считается (формально)

```python
NetworkEffectBonus = min(0.15,
    0.08 * (verified_given / total_tasks_last_24h) +
    0.07 * (verified_received / total_tasks_last_24h)
)
```

- `verified_given` — адаптеры, которые были приняты и использованы минимум 3 другими узлами
- `verified_received` — адаптеры от других, которые узел подтвердил и успешно применил

**Поощрение синергии:**
Узел, который отдал 8 проверенных адаптеров и принял 5, получает почти максимальный бонус + приоритет в выборе leader.

### 7. Safety Invariants

1. NetworkEffectBonus может быть начислен только за **верифицированные** обмены (подтверждены минимум 3 независимыми узлами).
2. Узел не может получить > 30 % своего Merit за счёт синергии (защита от «синергия-ферм»).
3. Все Synergy Proofs хранятся в Merkle-tree и могут быть аудитированы любым узлом.

### 8. Failure Modes и Mitigation

- **Partition > 300 сек** → узлы переходят в local-only mode, используют последний известный Merkle-root.
- **Sybil flood** → fraud penalty = -200 Merit + 30-дневный quarantine.
- **Greedy node** (только потребляет) → автоматический -0.12 к NetworkEffectBonus.

### 9. Интеграция с другими компонентами

- Bootstrapping Mechanism — в фазе 1–2 NetworkEffectBonus снижен в 3 раза.
- Merit Score Engine — вызывает расчёт NetworkEffectBonus после каждой задачи.
- GlobalFlowController — ограничивает трафик для узлов с низким Synergy Score.

---

**Документ готов.**

Теперь консенсус **явно и математически поощряет синергию** — это не декларация, а встроенный экономический механизм.
