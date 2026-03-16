# LS / Local Cognitive System (LCS) — Architecture

Этот документ описывает текущую архитектуру репозитория и то, как данные проходят через систему.

## High-Level Layers

1. **apps/** — приложения (entrypoints)
   - `apps/console/` — CLI runtime
   - `apps/ghostgpt/` — GUI overlay runtime

2. **python/modules/** — единый модульный слой
   - `audio/` → ingest/VAD
   - `stt/` → STT pipeline
   - `llm/` → LLM runtime (+ stability wrappers)
   - `agent/` → AgentLoop, cancellation, observability
   - `cognitive_flow/` → Presence + Transition + Liminal (Phase 8)
   - `hexagon_core/` → когнитивное ядро (beliefs/causal/mission/COT)
   - `shared/` → config loader и общие утилиты

3. **config/** — единая конфигурация
   - `base.yaml` → common defaults
   - `{console,ghostgpt}.yaml` → app overrides
   - `local.yaml` → local overrides (ignored)

## Cognitive Lifecycle (12 Layers Stack)

GhostGPT управляется 12-слойным когнитивным стеком, объединяющим восприятие, эмоции, память и метаболизм.

### Full Stack Diagram

```mermaid
graph TB
    subgraph Input_Processing[Input & Perception]
        L1[1. Perception]
        L10[10. Inference Router]
        L11[11. Hardware Abs]
        L11 --> L10 --> L1
    end

    subgraph Executive_Core[Executive Core]
        L5[5. AgentLoop]
        L4[4. Amygdala]
        L5 ↔ L4
        L1 --> L5
        L1 --> L4
    end

    subgraph Memory_Reasoning[Memory & Reasoning]
        L2[(2. Memory System)]
        L3[3. Reflection]
        L5 ↔ L2
        L2 ↔ L3
    end

    subgraph Metabolism_Consolidation[Metabolism & Consolidation]
        L6[6. Metabolism]
        L7[7. Sleep/Homeostasis]
        L8[8. Growth Axis]
        L9[9. Immune System]

        L3 --> L6
        L2 ↔ L6
        L7 --> L2
        L4 ↔ L7
        L6 --> L8
        L6 --> L9
    end

    subgraph Interface[Human Interface]
        L12[12. Human Interface]
        L12 ↔ L5
    end
```

### Data Flow (Typical)

1.  **Perception**: Audio/Text попадает в `InputParser`.
2.  **Amygdala**: Проверяет резонанс и уровень угрозы.
3.  **AgentLoop**: Оркестрирует вызов LLM через **Inference Router**.
4.  **Memory**: Сохраняет эпизод в Causal/Temporal графы.
5.  **Metabolism**: (В фоне или во сне) перерабатывает эпизод, укрепляя **Growth Axis**.

---

## Core LLM & Inference

### Qwen3.5 Small Series Integration
Система оптимизирована для работы с серией Qwen3.5 (от 0.8B до 9B параметров).
- **Qwen3.5-0.8B / 2B**: Используется для быстрых рефлексий и простых задач на Edge-устройствах.
- **Qwen3.5-4B / 9B**: Основная модель для сложного reasoning и интервью-копилота.

### Dynamic Model Size Policy (Planned)
Роутер (`ModelSizePolicy`) динамически переключает размер модели в зависимости от:
1.  Доступной RAM (через `RAMAwareSelector`).
2.  Сложности входящего запроса.
3.  Текущего уровня "энергии" агента (из Metabolism Layer).

---

## AgentLoop

`python/modules/agent/loop.py` — центральный “оркестратор” выполнения:
- Управляет состояниями: `idle/listening/thinking/responding/sleep`.
- **Cooperative Cancellation**: Новые вводы немедленно прерывают текущую генерацию.
- **Sleep Mode**: Автоматический переход в режим консолидации после 1800с инактивации.

## Cognitive Flow Layer (Phase 8+)

`python/modules/cognitive_flow/` — слой когнитивного потока:
- `presence.py` → Оперативное состояние (goal/phase/focus/intent/context).
- `transition_engine.py` → Фазные переходы reasoning.
- `liminal.py` → Пороговые состояния (Confusion/Aha!-moments).
- **Idle Yoga**: Периодическая глубокая рефлексия при длительном простое.

### Observability Contract v1

События, которые уходят в sink, нормализуются к контракту `1.0`.

Файл: `python/modules/agent/event_schema.py`

Обязательные поля:
- `type`: `input|output|cancel|state_change|metrics`
- `timestamp`: `float` (epoch seconds)
- `task_id`: `str`
- `version`: `"1.0"`
- `state`: `str | null`
- `payload`: `dict`

## LLM Layer

`python/modules/llm/` содержит runtime и защитные слои:
- `breaker.py`: circuit breaker (опционально)
- `cot_adapter.py`: адаптер reasoning-ядра (опционально)
- `llm_module.py`: основной runtime

## Hexagon Core

`python/modules/hexagon_core/` — когнитивные примитивы и подсистемы:
- beliefs lifecycle (устойчивость знаний)
- temporal queries / indexing
- causal graph
- mission state

Важно: ядро не должно зависеть от UI.

## Где меняется “поведение”

1. `llm.system_prompt` в YAML (или overrides в `config/local.yaml`)
2. feature flags в `config/base.yaml`
3. настройки agent loop (cancellation, metrics, observability)


## Planned Extension: Intent / Capability Routing Layer (ICRL)

Для масштабирования multi-agent режима вводится слой Intent Routing + Capability Index, который переводит топологию вызовов из статических связей в динамический capability matching.

См. RFC: `docs/RFC_INTENT_CAPABILITY_ROUTING_LAYER_RU.md`.
