# Transition Engine — Design Notes

Transition Engine управляет когнитивными переходами между фазами reasoning. Это не просто state‑machine статуса, а навигация между фазами мышления.

## Зачем

- предсказуемость reasoning‑потока
- управляемые переходы между фазами
- возможность “закрыть” фазу и “открыть” следующую
- интеграция liminal‑состояний

## Фазы (proposal v1)

- `perceive`
- `interpret`
- `analyze`
- `plan`
- `act`
- `reflect`

## Liminal состояния (межфазные)

Liminal — это короткие “пороговые” состояния между фазами:
- `perceive -> interpreting -> interpret`
- `analyze -> validating -> plan`
- `act -> checking -> reflect`

## Правила переходов (пример)

- `perceive -> interpret`
- `interpret -> analyze`
- `analyze -> plan`
- `plan -> act`
- `act -> reflect`
- `reflect -> perceive` (новый цикл)

