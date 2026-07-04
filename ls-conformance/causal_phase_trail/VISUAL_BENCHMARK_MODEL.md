# Visual Benchmark Axis

`VBA-001` adds a time-scoped external UI/UX benchmark to a causal phase trail.

It is orthogonal to the causal levels:

- `INDIVIDUAL`, `SYSTEM`, and `ENVIRONMENT` answer where an observation, cause, or constraint lives;
- `VISUAL_BENCHMARK` answers how the exact-head interface compares with current external guidance and exemplars for a named month or year.

```text
exact-head interface evidence
        +
current normative guidance
        +
current design-system guidance
        +
current trend and exemplar feed
        ↓
criterion-by-criterion gap analysis
        ↓
ADOPT / EXPERIMENT / DEFER / REJECT
        ↓
causal route candidate with expiry
```

## Source classes

- `NORMATIVE` — accessibility or other binding standards. Trend evidence may never override these constraints.
- `DESIGN_SYSTEM` — current official platform or design-system guidance.
- `TREND_FEED` — fast-moving current-month inspiration signals.
- `EXEMPLAR` — a specific external interface selected for comparison.

Every source has `capturedAt` and `validUntil`. Fast-moving trend and exemplar evidence is deliberately short-lived.

## Scoring

Each criterion has a 1-5 weight and a current/target score on a 0-5 scale. The validator recomputes:

```text
gap = targetScore - currentScore
weighted score = sum(score * weight) / sum(weight)
```

Scores are advisory. Every assessment also requires exact interface evidence, source references, an observation, and a recommendation.

## Pattern decisions

- `ADOPT` requires more than trend evidence alone.
- `EXPERIMENT` requires an explicit guard such as reduced-motion coverage, performance budget, contrast floor, exact-head screenshots, or a measurable outcome.
- `REJECT` preserves useful negative knowledge so the same fashionable but unsuitable pattern is not repeatedly reconsidered.

## Authority boundary

The axis is always `ADVISORY_ONLY` and `summary.mergeAuthority` is always `false`.

A monthly benchmark can propose a better visual route, but it cannot:

- weaken WCAG-backed behavior;
- invalidate green performance or browser evidence without new evidence;
- authorize merge;
- turn an award-site pattern into a product requirement;
- remain current after its `validUntil` date.

The first fixture compares Roby's PR #164 against July 2026 sources and identifies editorial product storytelling as the largest current visual gap while preserving the distinctive wordmark and rejecting novelty navigation.
