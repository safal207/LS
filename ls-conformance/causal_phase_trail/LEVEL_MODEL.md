# Causal Level Model

CPT-001 distinguishes three causal levels:

- INDIVIDUAL: human or agent observations, decisions, reviews, and corrective actions.
- SYSTEM: code, governance, evidence contracts, gates, and trust phase.
- ENVIRONMENT: external runtime capabilities and operating conditions.

The validated feedback loop is:

INDIVIDUAL -> SYSTEM -> ENVIRONMENT -> SYSTEM -> INDIVIDUAL

The overlay is defined by `causal-level-overlay.schema.json`, validated by `validate_levels.py`, instantiated in `fixtures/robys_pr_164_levels.json`, and tested by `tests/test_causal_levels.py`.

## Orthogonal benchmark axis

The time-scoped `VISUAL_BENCHMARK` is not a fourth causal level. It compares exact-head interface evidence with current normative guidance, design systems, trend feeds, and exemplars for a named month or year.

This separation prevents a current visual fashion from being mistaken for an environmental cause or from overriding normative accessibility, performance, browser, or governance evidence.
