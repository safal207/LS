# LCE_IN_LS.md
**Версия:** 1.0 (лучший вариант)  
**Дата:** 19 февраля 2026  
**Автор:** Главный архитектор LS

#### 1. Назначение

Внедрить **LCE (Liminal Context Envelope)** как **встроенный metadata-блок** в структуру Web4 RTT Message.

LCE — это **Layer 8 протокол присутствия**, который передаёт не только текст, но и:
- намерение
- эмоциональное состояние
- семантику
- нить разговора
- consent
- coherence
- **память путей** (trajectory_hint)

Это позволяет агенту учиться значительно быстрее, используя прошлые успешные и неудачные траектории, как это делает опытный человек.

#### 2. Почему этот вариант — лучший для LS

- **Встроенный** в RTT Message — минимум overhead, максимальная целостность.
- **Trajectory-aware** — агент помнит не только факты, а **пути** (состояние → действие → результат → урок).
- **Синергия-ready** — `synergy_hint` и `merit_domain` сразу влияют на роутинг и Merit Score.
- **Human-in-the-loop** по умолчанию.
- **Полная совместимость** с Web4 Mesh, GlobalFlow и меритократией.

#### 3. Структура Web4 RTT Message с LCE

```json
{
  "rtt_version": "1.0",
  "message_id": "msg_9f8a3b2e...",
  "trace_id": "trace_...",
  "payload": { ... },
  "lce": {
    "thread_id": "thread_550e8400...",
    "t": 1740003432,
    "intent": { "type": "ask", "goal": "..." },
    "affect": { "pad": [0.7, 0.4, 0.6], "tags": ["curious"] },
    "meaning": { "topic": "quantum", "ontology": "..." },
    "policy": { "consent": "full" },
    "qos": { "coherence": 0.92 },
    "ls_meta": {
      "merit_domain": "research",
      "synergy_hint": ["node_7a3f"],
      "trajectory_hint": {
        "past_successful": ["thread_abc123"],
        "avoid": ["thread_bad789"],
        "lessons": ["avoid overthinking when urgency high"]
      }
    }
  },
  "signature": "Ed25519..."
}
```

#### 4. Ключевые поля LCE и их роль в LS

| Поле LCE                       | Компонент LS                         | Как ускоряет обучение |
|--------------------------------|--------------------------------------|-----------------------|
| `intent`                       | Hexagon Core, AgentLoop              | Точная цель шага |
| `affect`                       | Shadow Layer                         | Эмоциональная подстройка |
| `meaning`                      | Beliefs Graph                        | Семантическая непрерывность |
| `thread_id`, `t`               | Temporal Index                       | Нить разговора |
| `policy.consent`               | HCP, Mesh                            | Consent-first |
| `qos.coherence`                | AdaptiveGovernor, ObservabilityHub   | Drift detection |
| `ls_meta.merit_domain`         | Merit Score Engine                   | Контекст вклада |
| `ls_meta.synergy_hint`         | Web4 Mesh Router                     | Умный роутинг |
| **`ls_meta.trajectory_hint`**  | **Shadow Layer + Hexagon Core**      | **Память путей** — главное ускорение |

#### 5. Как trajectory_hint ускоряет обучение

- `past_successful` — ссылки на успешные траектории (используются как few-shot примеры).
- `avoid` — ссылки на неудачные пути (избегаются).
- `lessons` — короткие выводы из прошлого опыта.

Shadow Layer автоматически использует эти данные при генерации ответа.  
Hexagon Core обновляет Beliefs Graph на основе новых уроков.  
Merit Score Engine даёт бонус за использование успешных траекторий.

Это делает обучение **экспоненциальным**, как у опытного человека.

---

Этот вариант — **лучший**, потому что:
- Минимальный overhead.
- Максимальная интеграция.
- Прямо решает задачу ускорения обучения через память путей.
