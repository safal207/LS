# Presence Layer — Design Notes

Presence — это слой “оперативного сознания”: удерживает цель, фазу reasoning, фокус и текущий контекст. Это не память и не beliefs. Это краткоживущий рабочий контур.

## Зачем

- непрерывность мышления между шагами
- удержание направления в рамках одной задачи
- явное текущее намерение
- снижение “reset” эффекта между turns

## Где живёт

Presence находится **над Temporal** и **под AgentLoop**:

```
Beliefs → Presence → Transition → Temporal → AgentLoop → Output
```

## Сущность PresenceState

Предлагаемая структура:
- `goal`: текущая цель (string)
- `phase`: когнитивная фаза (например: `perceive|interpret|analyze|plan|act|reflect`)
- `focus`: активный объект внимания (string)
- `intent`: краткое намерение (string)
- `context`: краткая свёртка контекста (string)
- `task_id`: активная задача (string)
- `confidence`: 0..1
- `updated_at`: timestamp

## Минимальный API

- `snapshot() -> dict`
- `set_goal(text)`
- `set_phase(phase)`
- `set_focus(text)`
- `set_intent(text)`
- `update_context(summary)`
- `reset(reason)`

## Интеграция

- AgentLoop должен иметь доступ к PresenceState
- Transition Engine обновляет `phase`
- Temporal фиксирует `updated_at`
- Observability может публиковать `presence` как метаданные (best‑effort)

## Семантика

- Presence не хранит долгосрочную память
- Presence сбрасывается при `idle` или по explicit reset
- Presence не влияет на LLM напрямую без явного шага в AgentLoop

