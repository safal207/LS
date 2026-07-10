# Reviewer Signal Weights

These weights compare reviewer contribution to PR decision confidence.

They are advisory. Required CI gates still dominate merge eligibility.

## Weight scale

```text
0   = no useful signal for this dimension
100 = strongest useful signal for this dimension
```

## Reviewer comparison

| Reviewer | Gate | Causal reasoning | Runtime | Security | Docs | Tone |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Security & CI Pipeline | 95 | 35 | 60 | 95 | 30 | 10 |
| Reflection Dashboard HTTP E2E | 80 | 25 | 90 | 25 | 20 | 5 |
| Grok PR Review | 35 | 90 | 35 | 45 | 70 | 80 |
| CodeRabbit | 20 | 45 | 20 | 30 | 75 | 65 |
| Human/agent synthesis | 70 | 95 | 70 | 70 | 85 | 90 |

## Decision rule

Required CI gates dominate merge eligibility. Advisory reviewers raise or lower confidence and can trigger follow-up commits when their causal findings are supported by evidence.

## How to use this with a causal graph

```text
CI gate signal
  -> merge eligibility

Runtime smoke signal
  -> runtime confidence

Advisory reasoning signal
  -> causal findings
  -> follow-up commits
  -> updated merge confidence

Human/agent synthesis
  -> evidence weighting
  -> final recommendation
```

## Boundary

These weights are heuristic and advisory. They help compare reviewer signals, but do not replace repository branch protection, test results, or human judgement.
