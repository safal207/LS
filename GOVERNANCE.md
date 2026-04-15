# Governance

This document describes lightweight governance for engineering and grant accountability.

## Roles

- **Maintainer**: approves architecture and release decisions.
- **Reviewer**: validates correctness, risk, and test coverage.
- **Security owner**: oversees vulnerability triage and remediation tracking.
- **Program owner**: tracks milestones, impact metrics, and grant deliverables.

One person may hold multiple roles in early-stage operation.

## Decision Process

- Prefer written proposals for significant changes (architecture, security policy, roadmap shifts).
- Use PR discussion as the canonical decision record.
- Resolve disagreements by impact-to-risk ratio and reproducibility evidence.

## Change Control

- All code changes land via PR.
- CI and required checks must pass before merge.
- Security- or workflow-related changes require explicit reviewer attention.

## Release Discipline

- Keep a changelog for each release.
- Include notable security and reliability changes.
- Use rollback notes for high-risk releases.

## Grant Accountability

- Maintain milestone tracking against promised deliverables.
- Publish periodic KPI snapshots from `IMPACT_METRICS.md`.
- Document deviations and corrective actions.

## Code of Conduct

Refer to `CONTRIBUTING.md` and repository norms for collaboration expectations.
