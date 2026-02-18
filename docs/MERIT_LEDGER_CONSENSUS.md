# MERIT_LEDGER_CONSENSUS.md
**Версия:** 0.3 (полный текст)
**Дата:** 18 февраля 2026
**Автор:** Главный архитектор LS

### 1. Назначение

Определить распределённый консенсус-протокол для **Global Merit Ledger**, который гарантирует сильную eventual consistency, честный расчёт NetworkEffectBonus и прозрачное поощрение синергии.

### 2. Threat Model

- Long-range partition (split-brain)
- Sybil + fake contributions
- Selective withholding данных (greedy nodes)
- Eclipse-атаки на high-Merit узлы
- Spam синергии (фейковые обмены)
- Replay-атаки на gossip

### 3. Design Principles

1. Synergy-first — активная синергия даёт приоритет в консенсусе и больший бонус.
2. Strong eventual consistency.
3. Economic incentive alignment — честная синергия всегда выгоднее эгоизма.
4. Minimal trust (работает при ≥70 % честных узлов).

### 4. Общая архитектура

Двухслойная модель:
- Layer 1 (Soft) — Gossip каждые 60 сек
- Layer 2 (Strong) — Merkle-root Broadcast каждые 300 сек

### 5. Формальный протокол

#### 5.1 Gossip Layer

Каждые 60 сек узел рассылает neighbour set (20–30 случайных + 5 high-Merit):
```python
message = {
    "node_id": "...",
    "merit_delta": {...},
    "synergy_proofs": [signed exchanges],
    "timestamp": ts,
    "signature": sig
}
```

#### 5.2 Merkle-root Broadcast

Каждые 300 сек выбирается leader:
```python
leader_score = merit * (1 + 2.0 * recent_synergy_ratio)
```

#### 5.3 Conflict Resolution

1. Наибольший суммарный Merit подписавших узлов.
2. Наибольший Synergy Score.
3. Timestamp как tie-breaker только если разница ≤ 30 секунд (drift проверяется относительно медианы последних 20 gossip-сообщений).

### 6. NetworkEffectBonus

```python
NetworkEffectBonus = min(0.15,
    0.08 * (verified_given / total_tasks_last_24h) +
    0.07 * (verified_received / total_tasks_last_24h)
)
```

### 7. Safety Invariants

1. NetworkEffectBonus начисляется только за верифицированные обмены (3 случайных узла с Merit ≥ 300, выбранных VRF).
2. Узел не может получить > 30 % Merit за счёт синергии.
3. Все Synergy Proofs хранятся в Merkle-tree и аудитируемы.

### 8. Failure Modes и Mitigation

- Partition > 300 сек → local-only mode с последним валидным Merkle-root.
- Sybil flood → -200 Merit + 30-дневный quarantine.
- Greedy node → -0.12 к NetworkEffectBonus.
- Clock skew → сообщения с drift > 30 сек от медианы последних 20 gossip отвергаются.

### 9. Интеграция с другими компонентами

- Bootstrapping Mechanism — в фазе 1–2 NetworkEffectBonus снижен в 3 раза.
- Merit Score Engine — вызывает расчёт NetworkEffectBonus после каждой задачи.
- GlobalFlowController — ограничивает трафик для узлов с низким Synergy Score.
