# Reusable Coordination Advisory Card

## Card purpose

A compact advisory card for any surface that needs a quick strategy-to-scene fit readout.

> Conceptual UI spec only; not an implemented component.

## Card fields

- `label`
- `readiness`
- `intervention_mode`
- `playbook_support`
- `top_risk_driver`
- `summary_reason` (one-line)

## Example card content

```yaml
coordination_advisory_card:
  label: fragile
  readiness: 0.59
  intervention_mode: stabilization_first
  playbook_support: medium
  top_risk_driver: coordination_risk
  summary_reason: scene is fragile: coordination risk is elevated and playbook grounding is limited
```

## Interpretation guidance

A human reader should immediately understand:

1. **Current coordination posture** (`label`, `readiness`).
2. **Recommended intervention stance** (`intervention_mode`).
3. **How supported the playbook is right now** (`playbook_support`).
4. **What is most likely to break execution quality** (`top_risk_driver`).
5. **Why this conclusion was reached** (`summary_reason`).

## Usage contexts

This card is intentionally reusable across:

- dashboard summary tiles,
- demo deck slides,
- product landing pages,
- operator review panels,
- case study visuals.

## Guardrails

- Advisory interpretation only.
- No policy approval or execution toggles.
- Keep fields bounded and contract-aligned.
