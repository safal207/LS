# Pseudo-UI Concept: Coordination Advisory Screen

## Screen purpose

This document describes a **conceptual product surface** for presenting the existing `coordination_advisory_summary` and traceable upstream outputs to a human operator.

> This is a pseudo-UI concept for demos/spec alignment, **not** an implemented production screen.

## Main layout (single screen)

### 1) Top summary band

Primary "decision-ready" strip shown first:

- `coordination_advisory_label`
- `coordination_readiness`
- `primary_intervention_mode`
- `playbook_support_level`
- `top_risk_driver`

**Intent:** let an operator understand the advisory posture in under 10 seconds.

### 2) Compact rationale area

One concise explanatory line:

- `summary_reason`

**Intent:** keep interpretation bounded and readable without forcing users to parse multiple upstream objects.

### 3) Traceability area

Small linked references back to upstream layers:

- `collective_coordination_snapshot`
- `bridge_stabilization_order`
- `bridge_playbook_advisory`

**Intent:** preserve audit/review confidence by showing where the summary came from.

### 4) Optional support section

Compact supporting fields for operators who need slightly more context:

- `dominant_bridge_type`
- `dominant_stabilization_mode`
- `playbook_alignment_label`
- `coordination_risk`

**Intent:** keep the main surface clean while allowing quick context checks.

## Compact example content (fintech/compliance scenario aligned)

```yaml
top_summary_band:
  coordination_advisory_label: fragile
  coordination_readiness: 0.59
  primary_intervention_mode: stabilization_first
  playbook_support_level: medium
  top_risk_driver: coordination_risk

compact_rationale:
  summary_reason: scene is fragile: coordination risk is elevated and playbook grounding is limited

traceability_refs:
  collective_coordination_snapshot: coordination_state_label=fragmented
  bridge_stabilization_order: dominant_stabilization_mode=high_priority_first
  bridge_playbook_advisory: playbook_alignment_label=partially_aligned

optional_support:
  dominant_bridge_type: stabilization_bridge
  dominant_stabilization_mode: high_priority_first
  playbook_alignment_label: partially_aligned
  coordination_risk: 0.71
```

## Why this screen matters

- **Easier operator review:** one bounded summary object instead of fragmented evidence browsing.
- **Faster alignment discussion:** product/compliance/ops can react to the same advisory frame.
- **Better handoff:** downstream systems can consume stable fields without parsing free text.
- **Preserves explainability:** top-line view stays tied to explicit upstream layers.

## Guardrails

- Concept remains **advisory-only**.
- No autonomous approval/execution controls are implied.
- No unsupported runtime behavior is introduced.
