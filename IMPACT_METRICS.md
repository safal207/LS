# Impact Metrics

This file defines operational and grant-facing metrics for LS.

## Measurement Principles

- Prefer objective, reproducible metrics over narrative claims.
- Track both engineering health and real operator outcomes.
- Keep a clear baseline, target, and reporting cadence.

## KPI Set

| KPI | Definition | Baseline | Target | Cadence |
|---|---|---:|---:|---|
| CI pass rate on `main` | Successful workflow runs / total runs | TBD | >= 95% | Weekly |
| Security remediation lead time | Median time from vuln detection to fix merge | TBD | <= 7 days | Monthly |
| Critical check flake rate | Re-run required due to non-deterministic failure | TBD | <= 2% | Weekly |
| Reproducible setup success | Fresh environment setup success rate | TBD | >= 90% | Monthly |
| Demo time-to-first-success | Time to complete canonical demo | TBD | <= 10 min | Monthly |
| Safety gate pass rate | Quality/safety workflow pass rate | TBD | >= 95% | Weekly |
| External pilot count | Active external evaluators or pilot partners | TBD | >= 3 | Quarterly |
| Evidence artifacts published | Public case studies/reports per quarter | TBD | >= 2 | Quarterly |

## Data Sources

- GitHub Actions run history and check summaries.
- Release and changelog artifacts.
- Structured test outputs and quality reports.
- Pilot logs and case-study notes (sanitized).

## Reporting Format

Each reporting cycle should include:

1. KPI table with baseline/current/target.
2. Notable regressions and root cause.
3. Corrective actions and owner.
4. Forecast for next cycle.

## Evidence Packaging for Grants

- Include latest KPI snapshot in grant appendices.
- Link each KPI to a reproducible source artifact.
- Annotate material assumptions and data limitations.
