# Grant Submission Template (English)

Use this template to prepare a funder-ready application package in 30-60 minutes.

---

## 1) Project Summary (150-250 words)

**Project name:** LS (GhostGPT / Local Cognitive System)

**Summary draft:**

LS is a local-first AI coordination and oversight runtime focused on reliability, safety, and auditability in human-plus-model workflows. The project addresses the gap between prototype AI agents and production-grade systems by integrating structured quality gates, reproducible evaluation workflows, and governance artifacts suitable for external review.  
  
Our near-term plan is to harden reliability and security operations, improve reproducibility of demos and tests, and publish measurable evidence through KPI reports and case studies. Funding will support engineering execution, evaluation infrastructure, and public evidence outputs that help independent reviewers assess both technical performance and risk controls.

---

## 2) Problem Statement

**Prompt:** What problem are you solving, for whom, and why now?

**Fill-in structure:**

- Target users/operators: `<who>`
- Current pain points: `<what fails today>`
- Why this is urgent now: `<market/regulatory/technical timing>`
- Consequence if unresolved: `<risk or lost opportunity>`

---

## 3) Proposed Work (6-12 months)

Use the work-package model from `GRANT_READINESS.md`.

### WP1: Reliability and Reproducibility
- Deliverable A: `<...>`
- Deliverable B: `<...>`
- Success criteria: `<quantified criteria>`

### WP2: Security and Risk Hardening
- Deliverable A: `<...>`
- Deliverable B: `<...>`
- Success criteria: `<quantified criteria>`

### WP3: Evaluation and Public Evidence
- Deliverable A: `<...>`
- Deliverable B: `<...>`
- Success criteria: `<quantified criteria>`

---

## 4) Milestones and Timeline

| Milestone | Date | Output |
|---|---|---|
| M1 | `<date>` | `<output>` |
| M2 | `<date>` | `<output>` |
| M3 | `<date>` | `<output>` |
| M4 | `<date>` | `<output>` |

---

## 5) Impact and KPIs

Reference `IMPACT_METRICS.md`.

Minimum KPI block to include:

- CI pass rate on main
- Security remediation lead time
- Critical check flake rate
- Reproducible setup success rate
- Safety gate pass rate
- External pilot count

For each KPI provide:
- baseline,
- target,
- measurement cadence,
- data source.

---

## 6) Risk and Mitigation

Reference:
- `THREAT_MODEL.md`
- `SECURITY.md`

Suggested table:

| Risk | Severity | Mitigation | Owner |
|---|---|---|---|
| `<risk>` | `<level>` | `<plan>` | `<name/role>` |

---

## 7) Governance and Team Capacity

Reference `GOVERNANCE.md`.

Include:

- key roles and decision process,
- change control and review discipline,
- release and reporting cadence.

---

## 8) Budget Narrative (Non-sensitive)

Use simple categories:

- Engineering execution
- Security and reliability operations
- Evaluation and reporting
- Program management/documentation

Describe why each category is necessary for milestone delivery.

---

## 9) Evidence Attachments

Attach or link:

- one-pager (`docs/grants/ONE_PAGER_EN.md`),
- roadmap (`ROADMAP.md`),
- changelog (`CHANGELOG.md`),
- KPI framework (`IMPACT_METRICS.md`),
- security and threat docs (`SECURITY.md`, `THREAT_MODEL.md`).

---

## 10) Final Funder Checklist

- [ ] Problem statement is specific and measurable.
- [ ] Work packages map to milestones and budget categories.
- [ ] KPIs include baseline and target.
- [ ] Risks and mitigations are explicit.
- [ ] Governance and delivery ownership are clear.
- [ ] Linked artifacts are public and reproducible.
