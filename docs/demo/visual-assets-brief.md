# Visual Assets Brief (for Future Figma/Canva Mockups)

## Scope

Create simple visual artifacts that represent the **existing advisory outputs** of the coordination stack.

> This brief is for concept visuals only; it does not imply a shipped UI.

## Target visuals (2–3)

### 1) Coordination Advisory Screen concept (single screen)
- **Audience:** operators, product leaders, compliance stakeholders.
- **Must show:** top summary band, summary reason, traceability links, optional support fields.
- **Goal:** make the advisory output immediately reviewable.

### 2) Reusable advisory card
- **Audience:** dashboard and GTM/marketing contexts.
- **Must show:** label, readiness, intervention mode, playbook support, top risk driver, one-line reason.
- **Goal:** portable summary artifact for multiple surfaces.

### 3) Before/After comparison slide
- **Audience:** demo/pitch conversations.
- **Must show:** fragmented multi-tool workflow vs one bounded advisory object.
- **Goal:** communicate value quickly.

## Required fields (contract-aligned)

Use only currently supported semantics:

- `coordination_advisory_label`
- `coordination_readiness`
- `primary_intervention_mode`
- `playbook_support_level`
- `top_risk_driver`
- `summary_reason`
- optional trace/support: `coordination_risk`, `dominant_bridge_type`, `dominant_stabilization_mode`, `playbook_alignment_label`

## Style guidance

- clean and minimal,
- audit-friendly,
- product-operator oriented,
- clear typography hierarchy,
- restrained color usage for risk/readiness emphasis.

## Avoid

- sci-fi control room aesthetics,
- fake autonomous approval/execution controls,
- dense dashboard clutter,
- unsupported capability claims,
- fake "live" screenshots.
