# LCE_IN_LS.md
**Версия:** 1.3 (лучшая финальная)  
**Дата:** 19 февраля 2026  
**Автор:** Главный архитектор LS

### 1. Назначение

Внедрить **LCE (Liminal Context Envelope)** как встроенный metadata-блок в структуру Web4 RTT Message.

LCE — это **Layer 8 протокол присутствия**: он передаёт не только текст, но и намерение, эмоциональное состояние, семантику, нить разговора, consent и coherence — всё в одном объекте, который летит с каждым сообщением.

### 2. Почему встроенный LCE — лучший вариант для LS

- Минимализм: один RTT-объект вместо payload + внешнего envelope.
- Нативная интеграция: все компоненты LS читают `message.lce` напрямую.
- Coherence-by-default: ObservabilityHub сразу считает drift.
- Synergy-ready: `merit_context` и `synergy_hint` доступны Mesh Router и Merit Engine без трансформаций.
- Governance-safe: human-in-the-loop и consent-first встроены на уровне протокола.

### 3. Архитектурное место LCE

```mermaid
graph TD
    Human[Человек] --> RTT[Web4 RTT Message + встроенный LCE]
    RTT --> Runtime[Web4 Runtime]

    Runtime --> Hub[ObservabilityHub]
    Runtime --> Flow[GlobalFlowController]

    Hub --> Hex[Hexagon Core]
    Hub --> Shad[Shadow Layer]
    Hub --> Gov[AdaptiveGovernor]

    Flow --> Merit[Merit Score Engine]
    Merit --> Mesh[Web4 Mesh Router]

    Mesh --> Other[Другие узлы сети]

    Gov --> Auto[Auto-tune + human approval]
```

### 4. LCE как Шесть Путей Современного Мудреца

Метафора «Шести Путей» фиксирует ключевой принцип LS:  
**сила системы не должна быть заперта в одном узле**. Она должна распределяться, передаваться и усиливаться через сеть.

Как Мудрец Шести Путей разделил свою силу, чтобы она жила дальше, так и мы делаем LCE носителем присутствия, которое течёт через всю систему.

| Путь                  | Поле LCE                     | Что передаёт дальше |
|-----------------------|------------------------------|---------------------|
| Путь Разума           | `intent` + `meaning`         | Цель и семантика |
| Путь Эмоций           | `affect`                     | Эмоциональное присутствие |
| Путь Памяти           | `thread_id` + `t`            | Нить непрерывности |
| Путь Согласия         | `policy.consent`             | Consent-first |
| Путь Качества         | `qos.coherence`              | Drift detection |
| Путь Синергии         | `merit_context` + `synergy_hint` + `trajectory_hint` | Меритократия и память путей |

### 5. Нормативная структура Web4 RTT Message (v1 + LCE)

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
      "synergy_hint": ["node_7a3f", "node_9c2d"],
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

### 6. Поля LCE и маршрутизация

| Поле LCE               | Компонент LS                  | Эффект |
|------------------------|-------------------------------|--------|
| `intent`               | Hexagon Core, AgentLoop       | Точная целевая интерпретация |
| `affect`               | Shadow Layer                  | Эмоциональная калибровка ответа |
| `meaning`              | Beliefs Graph                 | Семантическая непрерывность |
| `thread_id`, `t`       | Temporal Index                | Непрерывность между сессиями |
| `policy.consent`       | HCP, Hub, Mesh                | Consent-first enforcement |
| `qos.coherence`        | ObservabilityHub, AdaptiveGovernor | Drift detection |
| `ls_meta.merit_domain` | Merit Score Engine            | Контекстная оценка вклада |
| `ls_meta.synergy_hint` | Web4 Mesh Router              | Soft-priority роутинга |
| `ls_meta.trajectory_hint` | Shadow Layer + Hexagon Core | Память путей и ускорение обучения |

### 7. План внедрения (Phase 15–16)

1. Добавить обязательное поле `lce` в RTT Message (Rust + Python).
2. Обновить сериализацию/подпись RTT.
3. Расширить ObservabilityHub до LSS.
4. Подключить чтение LCE в Shadow Layer и AdaptiveGovernor.
5. Включить `synergy_hint` и `trajectory_hint` в Mesh Router.

### 8. Definition of Done

- Все RTT-сообщения содержат валидный `lce` блок.
- Корреляция по `trace_id` и `thread_id` работает end-to-end.
- AdaptiveGovernor делает минимум один тюнинг через human approval.
- Зафиксировано measurable improvement по coherence/latency/error-rate.
- Trajectory memory используется как центр ориентации путей и снижает повтор ошибок.
