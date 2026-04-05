# Fintech Release Demo Expected Output (Compact Excerpts)

This document shows compact, layer-by-layer excerpts for the canonical fintech release scenario.

> **Important:** excerpts below use current contract-compatible value domains from the coordination stack. Values are illustrative but enum labels are literal.

## Layer 1: `multi_party_alignment_state`

```yaml
multi_party_alignment_state:
  state_label: diverging
  dominant_tension_axis: speed_vs_review_confidence
  alignment_convergence: 0.52
  adoption_coverage: 0.67
  summary_reason: cross-functional goals are partially aligned, but release speed and review confidence remain in active tension
```

## Layer 2: `bridge_stabilization_order`

```yaml
bridge_stabilization_order:
  dominant_stabilization_mode: high_priority_first
  ordered_edges:
    - rank: 1
      from_party_id: product
      to_party_id: compliance_risk
      stabilization_label: urgent_stabilize
      recommended_timing: now
    - rank: 2
      from_party_id: product
      to_party_id: operations
      stabilization_label: early_stabilize
      recommended_timing: soon
  summary_reason: mode=high_priority_first; total_edges=4; urgent=1; early=2; quick=0; defer=1
```

## Layer 3: `collective_coordination_snapshot`

```yaml
collective_coordination_snapshot:
  coordination_state_label: fragmented
  coordination_risk: 0.71
  dominant_bridge_type: stabilization_bridge
  dominant_stabilization_mode: high_priority_first
  summary_reason: scene remains coordination-fragile due to unresolved confidence and rollout pacing conflicts
```

## Layer 4: `bridge_playbook_advisory`

```yaml
bridge_playbook_advisory:
  playbook_alignment_label: partially_aligned
  playbook_alignment_score: 0.62
  dominant_bridge_playbook_fit: stabilization-led
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
  summary_reason: scene is fragile: coordination risk is elevated and playbook grounding is limited
```

## Short interpretation

The stack moves from fragmented party-level tension to an ordered stabilization path, then to a collective snapshot, and finally to one compact advisory summary. In this scenario, there is enough structure to proceed, but only with stabilization-first sequencing rather than immediate full-speed execution.
