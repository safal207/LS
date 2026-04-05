# Fintech Release Demo Sample Data (Illustrative)

This document provides a compact, reusable sample input set for the canonical fintech release scenario.

> **Important:** all values below are illustrative demo data, not production customer data.

## A) Alignment report sketch

```yaml
alignment_report:
  overall_alignment_score: 0.54
  tension_score: 0.69
  participant_states:
    - participant: product
      stance: push_release
      confidence: 0.81
      primary_driver: timeline_commitment
    - participant: compliance_risk
      stance: require_more_review_confidence
      confidence: 0.78
      primary_driver: threshold_validation_gap
    - participant: operations
      stance: caution_on_rollout
      confidence: 0.72
      primary_driver: rollback_complexity
    - participant: engineering_security
      stance: add_one_hardening_check
      confidence: 0.74
      primary_driver: unresolved_hardening_item
  pairwise_hotspots:
    - pair: [product, compliance_risk]
      hotspot_score: 0.82
      mismatch_reason: speed_vs_review_confidence
    - pair: [product, operations]
      hotspot_score: 0.76
      mismatch_reason: launch_speed_vs_rollout_safety
    - pair: [product, engineering_security]
      hotspot_score: 0.68
      mismatch_reason: deadline_vs_hardening_completion
    - pair: [compliance_risk, operations]
      hotspot_score: 0.41
      mismatch_reason: mostly_aligned_on_caution
```

## B) Playbook seed recommendations

```yaml
playbook_seed_recommendations:
  - id: staged_rollout_with_hold_points
    rationale: reduce operational blast radius while preserving release momentum
    expected_effect: lowers rollout instability risk
  - id: evidence_first_review_bundle
    rationale: package threshold-change validation evidence for compliance/risk
    expected_effect: improves review confidence before wide release
  - id: hardening_check_gate_before_scale
    rationale: complete one pending hardening check before full traffic exposure
    expected_effect: lowers security-driven release objections
```

## C) Adoption traces

```yaml
adoption_traces:
  - intervention: staged_rollout_with_hold_points
    adoption_label: partial_adoption
    adoption_score: 0.63
    note: ops_and_engineering_positive_product_requests_tighter_timeline
  - intervention: evidence_first_review_bundle
    adoption_label: strong_adoption
    adoption_score: 0.79
    note: compliance_risk_signals_higher_confidence_if_bundle_is_complete
  - intervention: hardening_check_gate_before_scale
    adoption_label: conditional_adoption
    adoption_score: 0.58
    note: accepted_if_check_finishes_within_release_window
```

## D) Bridge / stabilization interpretation hints

Expected interpretation hints for demo narration:

- Dominant bridge pressure is **Product ↔ Compliance/Risk** (speed vs review confidence).
- Next stabilization edge is **Product ↔ Operations** (pace vs rollback safety).
- Engineering/Security acts as a bridging constraint amplifier rather than an isolated blocker.
- Likely intervention mode trends toward **stabilization-first** rather than immediate full rollout.
