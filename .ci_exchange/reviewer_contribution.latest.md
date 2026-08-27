# Reviewer Contribution Scorecard — PR #856

This scorecard compares **actual validated contribution on this PR**, not general reviewer quality.

## Causal model

```text
review finding
  -> human/agent confirmation
  -> severity assessment
  -> uniqueness check
  -> accepted code change
  -> test evidence
  -> contribution points
  -> reviewer comparison
```

## Formula

```text
finding score =
severity points
× outcome multiplier
× (0.40 + 0.25×actionability + 0.20×causal depth + 0.15×uniqueness)
```

Severity:

```text
high = 5
medium = 3
low = 1
```

## Current comparison

| Reviewer | Confirmed findings | Contribution points | Share |
| --- | ---: | ---: | ---: |
| Qodo | 3 | 12.38 | 80.7% |
| Grok PR Review | 1 | 2.78 | 18.1% |
| CodeRabbit | 0 | 0.18 | 1.2% |
| LS multi-model review | 0 | 0.00 | 0.0% |

## Why Qodo leads on this PR

Qodo found two unique high-severity reliability issues:

- missing committed outputs caused a raw traceback in `--check` mode;
- malformed or missing metadata could abort health-report generation.

It also independently confirmed the per-check status problem first surfaced through Grok. Because the duplicate finding is only half-unique, it receives reduced uniqueness credit.

## Why Grok still mattered

Grok triggered the key causal correction:

```text
one global status
  -> misleading per-check health
  -> grouped validation errors
  -> truthful per-section status
```

That finding directly changed the architecture of the report.

## Why summaries score lower

CodeRabbit provided useful walkthrough, documentation, and PR-template signals, but those did not produce an accepted correctness fix in this PR. Summary volume is deliberately not treated as engineering contribution.

The LS multi-model lane produced no structured finding because its provider credential was not configured. No execution means no contribution credit for this PR.

## Boundary

These numbers are PR-specific. They must change if a finding is rejected, reverted, duplicated by earlier evidence, or later shown to be incorrect. Required CI checks remain separate from reviewer contribution scores.
