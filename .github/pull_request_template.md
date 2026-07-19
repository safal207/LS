## What changed?

Briefly describe the change.

## Type of change

- [ ] Landing page
- [ ] Documentation
- [ ] Runtime / backend
- [ ] Tests / CI
- [ ] Community task / issue cleanup

## Why it matters

Explain the visitor, contributor, operator, or safety value.

## Checks

- [ ] I ran the smallest relevant local check.
- [ ] I updated docs or screenshots if the user-facing surface changed.
- [ ] I kept the PR focused.

## Exact-head validation

**Exact PR head SHA validated:**

<!-- Paste the full 40-character PR head SHA covered by the evidence below. -->

**Validation command:**

```text

```

- [ ] Validation was run or rerun after the most recent PR head change.
- [ ] Evidence, screenshots, and expected output apply to the exact SHA above.

> Evidence becomes stale when the PR head, evaluated inputs, environment, authorization, or relevant dependency state changes. Rerun validation before review or merge.

## Lotus check 🌸

> **Does this change increase intelligence without reducing human freedom?**

- [ ] This change does not introduce hidden authority, weaken privacy, or present uncertainty as fact.
- [ ] Any durable memory, automated action, or consequential decision remains inspectable, challengeable, and human-governed.
- [ ] The assistant or automation does not gain ownership, approval, execution, delivery, or merge authority.

**Lotus note — one concrete sentence:**

<!-- Describe a real design choice or tradeoff, not just agreement with the principle. Example: "The new memory lane is advisory-only, exposes its evidence digest, and cannot raise the verdict to PASS." Write "Not applicable" only for genuinely routine maintenance. See LOTUS.md. -->

## Lotus Product Lens — when applicable

Use this section for changes to user journeys, offers, pricing, checkout, paid add-ons, follow-up offers, subscriptions, recovery, or growth experiments. See [`docs/LOTUS_PRODUCT_LENS.md`](../docs/LOTUS_PRODUCT_LENS.md).

- [ ] Not applicable — the Lotus note explains why.
- [ ] Applicable — the user goal and business goal are both explicit.
- [ ] Price, recurring terms, decline path, and refund or recovery path are visible before commitment.
- [ ] Any add-on, upgrade, upsell, or downsell is relevant, optional, and not preselected.
- [ ] Conversion, AOV, LTV, retention, refund, or churn claims name the exact experiment, cohort, denominator, time window, and uncertainty.
- [ ] No false urgency, obstructed decline, surprise payment, or excessive recovery messaging is introduced.

For landing changes:

```bash
cd ghostgpt-ls-landing
npm run build
```

## Screenshots or evidence

Add before/after screenshots, exact-head test output, evidence artifacts, or other relevant proof.
