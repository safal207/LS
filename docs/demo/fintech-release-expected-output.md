# Fintech Release Demo Expected Output (Compact Excerpts)

This document shows compact, layer-by-layer excerpts for the canonical fintech release scenario.

> **Important:** excerpts are illustrative and intentionally compact for demo readability.

## Layer 1: `multi_party_alignment_state`

```yaml
multi_party_alignment_state:
  state_label: contested_alignment
  dominant_tension_axis: speed_vs_review_confidence
  alignment_convergence: 0.52
  adoption_coverage: 0.67
  summary_reason: cross-functional goals are partially aligned, but release speed and review confidence remain in active tension
```

## Layer 2: `bridge_stabilization_order`

```yaml
bridge_stabilization_order:
  dominant_stabilization_mode: deescalate_then_sequence
  top_ordered_edges:
    - edge: [product, compliance_risk]
      priority: 1
      reason: highest hotspot and gating effect on release confidence
    - edge: [product, operations]
      priority: 2
      reason: rollout safety concerns shape executable pacing
  summary_reason: stabilize review-confidence bridge first, then sequence rollout-risk bridge
```

## Layer 3: `collective_coordination_snapshot`

```yaml
collective_coordination_snapshot:
  coordination_state_label: fragile_under_deadline_pressure
  coordination_risk: 0.71
  dominant_bridge_type: confidence_bridge
  dominant_stabilization_mode: deescalate_then_sequence
  summary_reason: scene remains coordination-fragile due to unresolved confidence and rollout pacing conflicts
```

## Layer 4: `bridge_playbook_advisory`

```yaml
bridge_playbook_advisory:
  playbook_alignment_label: partially_supported
  playbook_alignment_score: 0.62
  dominant_bridge_playbook_fit: evidence_first_then_staged_rollout
  summary_reason: playbook supports the dominant bridge pattern, but support is incomplete until hardening gate is closed
```

## Layer 5: `coordination_advisory_summary`

```yaml
coordination_advisory_summary:
  coordination_advisory_label: fragile
  coordination_readiness: 0.59
  primary_intervention_mode: stabilization_first
  playbook_support_level: medium
  top_risk_driver: coordination_risk
  summary_reason: scene is fragile: review-confidence and rollout-safety pressure remain above stable threshold
```

## Short interpretation

The stack moves from fragmented party-level tension to an ordered stabilization path, then to a collective snapshot, and finally to one compact advisory summary. In this scenario, the meaning evolution is consistent: there is enough structure to proceed, but only with stabilization-first sequencing rather than immediate full-speed execution.
