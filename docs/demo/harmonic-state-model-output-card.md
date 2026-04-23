# Reusable Harmonic State Card

## Card purpose

A compact structural diagnostics card for any surface that needs to explain *what kind* of tension a scene has, not only how much.

> Conceptual UI spec only; not an implemented component.

## Card fields

- `harmonic_center`
- `interval_label`
- `harmonic_tension`
- `harmonic_stability`
- `resolution_direction`
- `modulation_candidate`
- `harmonic_summary_reason` (one-line)

## Example card content

```yaml
harmonic_state_card:
  harmonic_center: stabilization
  interval_label: tritone
  harmonic_tension: 0.79
  harmonic_stability: 0.38
  resolution_direction: deescalate_then_translate
  modulation_candidate: translation
  harmonic_summary_reason: center is stabilization; scene is structurally dissonant and points toward translation
```

## Interpretation guidance

A human reader should immediately understand:

1. **Current tonal center** (`harmonic_center`).
2. **Type of structural relation** (`interval_label`).
3. **How loaded the scene is** (`harmonic_tension`).
4. **How much support it has** (`harmonic_stability`).
5. **What transition logic is recommended** (`resolution_direction`, `modulation_candidate`).
6. **Why the model reached that reading** (`harmonic_summary_reason`).

## Usage contexts

This card is intentionally reusable across:

- dashboard diagnostics panels,
- architecture review decks,
- operator review panels,
- bug triage case studies,
- product demos and landing pages.

## Guardrails

- Advisory interpretation only.
- No policy approval or execution toggles.
- Keep interval labels bounded and contract-aligned.
