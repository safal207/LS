# BOOTSTRAPPING_MECHANISM.md
**Версия:** 0.5 (готов к коммиту)
**Дата:** 18 февраля 2026
**Автор:** Главный архитектор LS

### 1. Назначение

Определить безопасный, детерминированный механизм запуска Web4 Meritocracy Mesh от состояния «1 узел» до критической массы (~10 000 активных узлов), после которой сеть полностью переходит в режим чистой меритократии без каких-либо специальных привилегий и флагов.

### 2. Угрозы Bootstrap Phase

- Массовый Sybil (один субъект создаёт тысячи узлов)
- Merit farming на начальных задачах
- Eclipse-атаки на ранние узлы
- Poisoned initial data / адаптеры
- Централизация (все первые узлы под контролем одной группы)
- Cold-start routing starvation новых узлов

### 3. Фазы Bootstrap

| Фаза              | Кол-во узлов | Продолжительность | Ключевые правила |
|-------------------|--------------|-------------------|------------------|
| **0. Genesis**    | 0–100        | до 30 дней        | Только Genesis Nodes |
| **1. Early Growth** | 100–2 000  | 30–90 дней        | Hybrid routing + Trusted Flag |
| **2. Ramp-up**    | 2 000–10 000 | 90–180 дней       | Progressive Multiplier + behavioral analysis |
| **3. Full Meritocracy** | >10 000 | —                 | Полный Merit Score v0.3 без исключений |

### 4. Genesis Nodes

- Создаются только core team + проверенные early contributors.
- Требуется **HCP Strong Attestation** (hardware root + human identity binding).
- Начальный Merit = **500** (фиксировано).
- Временный **Trusted Flag** (действует ровно 90 дней).

### 5. Progressive Merit Accrual (v0.5)

```python
def initial_merit(age_days: int, performance: float, is_genesis: bool) -> int:
    if is_genesis:
        return 500

    base = 30

    # Ramp-up: новые узлы получают меньше, стабильные — больше
    if age_days <= 7:
        multiplier = 0.35
    elif age_days <= 30:
        multiplier = 0.65
    elif age_days <= 90:
        multiplier = 0.90
    else:
        multiplier = 1.00

    raw = base * multiplier * performance
    return max(10, int(raw))
```

**performance** = successful_tasks / total_tasks за последние min(20, available) задач.
Если задач < 5 → фиксировано 0.50.

**Cap на суммарный Merit** (применяется после каждого accrual):
```python
if not is_genesis and completed_tasks < 50:
    merit = min(100, merit)
```

### 6. Initial Routing (Bootstrap Routing)

- 60 % задач — deterministic (Genesis Nodes + Trusted Flag + текущий Merit)
- 30 % задач — exploration mode (weighted random среди узлов с Merit ≥ 30)
- 10 % задач — pure random (для новых узлов без истории)

### 7. Sybil Mitigation на Bootstrap

- Hardware + HCP Binding обязательно для Merit > 30.
- **Social Proof rate limit**: один узел может выдать максимум **5 рекомендаций** за любые 30 дней (+40 Merit новому узлу). Рекомендатель теряет 10 Merit при fraud на рекомендованном узле.
- Behavioral fingerprinting первых 50 задач.

### 8. Safety Invariants (v0.5)

1. Суммарный Merit всей сети растёт **только** через реально выполненные и валидированные задачи.
2. Ни один **не-Genesis** узел не может превысить Merit = 100 через per-task accrual без минимум 50 выполненных задач (cap применяется к суммарному Merit).
3. Genesis Nodes автоматически теряют Trusted Flag через 90 дней.
4. Все изменения правил bootstrap после Phase 1 требуют минимум 3 из 5 подписей от публично известных ключей Core Team.

### 9. Критерии перехода в Full Meritocracy

- ≥ 10 000 активных узлов
- Средний возраст сети ≥ 45 дней
- Gini коэффициент распределения Merit ≤ **0.55**
- 0 подтверждённых Sybil-атак за последние 30 дней
- Средний Task Success Rate ≥ 94 %

### 10. Интеграция с существующими компонентами

- GlobalFlowController — ограничивает нагрузку на ранние узлы.
- HCP — источник human attestation.
- Merit Score Engine — вызывается только после завершения bootstrap для конкретного узла.
- Web4 Mesh Router — получает флаг `is_bootstrapping_mode`.
