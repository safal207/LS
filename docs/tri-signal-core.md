# Tri-Signal Core

`Tri-Signal Core` is a minimal, deterministic cognition primitive for LS. It extracts three **independent ternary signals** from text using explicit markers.

## Axes

1. **Agreement axis**: `yes | no | neutral`
2. **Desire axis**: `want | dont_want | neutral`
3. **Meaning axis**: `meaningful | meaningless | neutral`

## Why these axes are independent

A speaker can agree with a plan but not want to do it. A speaker can want something they also consider pointless. A speaker can disagree while still seeing meaning in the topic. These are separate dimensions, so the model keeps them separate.

## Why neutral matters

`neutral` is a first-class result, not a failure state. It captures uncertainty, lack of explicit signal, or intentionally non-committal language. This keeps downstream logic from over-interpreting weak text.

## Example combinations

- `agreement=yes`, `desire=want`, `meaning=meaningful`: aligned commitment.
- `agreement=yes`, `desire=dont_want`, `meaning=meaningful`: cognitive friction (accepts value, resists action).
- `agreement=no`, `desire=want`, `meaning=meaningful`: motivation with disagreement on framing or method.
- `agreement=neutral`, `desire=neutral`, `meaning=neutral`: no clear signal.

## Example (requested)

Input:

`Надо заняться проектом. Да, это важно, но не хочу — устал.`

Expected shape:

- `agreement = yes`
- `desire = dont_want`
- `meaning = meaningful`

## Rule model notes

- Marker search spans `utterance`, `task_intent`, `scene_context`, and `recent_memory`.
- Negative markers are evaluated before positive ones on each axis.
- Confidence heuristic:
  - `0.8` direct marker
  - `0.6` supporting/indirect marker
  - `0.3` neutral default
- The output includes tension flags and a short readable summary.
