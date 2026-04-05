# LS Coordination Demo Walkthrough (3–5 minutes)

## Demo goal

Show, in one short run, that LS turns a messy coordination situation into a compact, explainable advisory summary that helps choose the next action.

## Audience takeaway

By the end of the demo, the audience should understand:
- what coordination problem LS solves,
- what layers LS builds,
- what the final advisory summary looks like,
- why this is better than a generic free-form assistant answer.

---

## 1) Starting situation (0:00–0:40)

Narration:
> "We have a high-stakes release with cross-functional tension: product wants speed, compliance wants stronger review, and operations sees increasing coordination risk."

Show:
- short scenario card with participants, constraints, and timeline pressure.
- mention that we are not asking for full autonomous execution; we need a reliable advisory readout first.

## 2) Which layers are built (0:40–1:30)

Narration:
> "LS processes the same scene through a bounded advisory chain, so the output is structured and reviewable."

Show sequence:
1. `multi_party_alignment_state`
2. `bridge_stabilization_order`
3. `collective_coordination_snapshot`
4. `bridge_playbook_advisory`
5. `coordination_advisory_summary`

Key line:
> "Each layer narrows ambiguity and prepares a compact decision object."

## 3) What the system sees (1:30–2:20)

Narration:
> "Instead of generic text, LS maps concrete coordination signals."

Highlight example signals:
- fragmentation pressure,
- bridge readiness,
- stabilization priority,
- playbook grounding level,
- conflict between urgency and governance constraints.

Key line:
> "This is interpretation of coordination state, not just summarization."

## 4) How playbook fit is produced (2:20–3:05)

Narration:
> "LS evaluates whether the chosen playbook fits this specific scene now."

Show:
- candidate playbook,
- fit assessment,
- support level and caveats,
- top risk driver if executed immediately.

Key line:
> "We get explicit fit quality, not implicit confidence vibes."

## 5) Final advisory summary (3:05–4:00)

Narration:
> "Now we have a decision-ready advisory object."

Example output (illustrative):

```json
{
  "coordination_advisory_label": "fragile",
  "coordination_readiness": 0.42,
  "primary_intervention_mode": "stabilization_first",
  "playbook_support_level": "medium",
  "top_risk_driver": "fragmentation_pressure",
  "summary_reason": "scene is fragile: coordination risk is elevated and playbook grounding is limited"
}
```

## 6) Why this matters (4:00–5:00)

Narration:
> "In under five minutes we moved from noisy context to a compact, explainable recommendation frame."

Value callout:
- faster alignment across product/compliance/ops,
- clearer next-step discussion,
- stronger audit/review traceability,
- better human + agent handoff object.

Close:
> "LS is not another chatbot. It is a coordination advisory compression layer for high-stakes decisions."

---


## Canonical scenario pack (fintech/compliance wedge)

For a reusable demo baseline, use:
- `docs/demo/fintech-release-scenario.md`
- `docs/demo/fintech-release-sample-data.md`
- `docs/demo/fintech-release-expected-output.md`
- `docs/demo/fintech-demo-checklist.md`
- `docs/demo/coordination-advisory-ui-concept.md`
- `docs/demo/coordination-advisory-output-card.md`
- `docs/demo/before-after-coordination-view.md`

## Optional live demo checklist

- Prepare one scenario card (participants, constraints, urgency).
- Preload or mock intermediate layer outputs.
- Keep one final advisory JSON ready on screen.
- End with one practical decision question: "Do we stabilize first or execute now?"

## Anti-patterns to avoid during demo

- Do not overfocus on model internals.
- Do not present LS as autonomous policy executor.
- Do not expand into many scenarios; show one scenario end-to-end.
- Do not replace structured outputs with only narrative prose.
