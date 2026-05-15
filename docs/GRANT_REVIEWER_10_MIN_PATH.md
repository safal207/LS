# LS Grant Reviewer 10-Minute Path

This is the fastest path for a grant reviewer to evaluate the current LS / Personal Cognitive Garden evidence package.

## 1. What problem does LS solve?

Continuous AI work creates a new governance problem: models begin to infer a person's goals, skills, weaknesses, motivation, decisions, and growth paths.

Without a governance layer, those inferences can silently become:

- durable memory;
- unauthorized profiling;
- employer-facing performance evaluation;
- opaque claims about a person's development;
- actions taken from broken or insufficient context.

LS studies a local-first runtime boundary for this problem: AI may propose memory, skill, or development updates, but only evidence-backed, human-reviewed, consent-bounded updates become durable personal state.

## 2. Core research question

```text
How can AI-assisted sessions compound human development without turning personal growth into surveillance, hidden scoring, or unauthorized memory?
```

The current grant-facing package focuses on Personal Cognitive Garden:

```text
AI session
-> development classification
-> proposed cognitive-garden update
-> human review
-> accepted/rejected private graph state
-> consent-bounded export policy
```

## 3. One-command local reproduction

From the repository root:

```bash
make grant-evidence
```

This command writes a reviewer-facing evidence bundle into:

```text
reports/grant_evidence/
```

Expected files:

```text
reports/grant_evidence/pcg_demo_output.json
reports/grant_evidence/pcg_red_team_block_output.json
reports/grant_evidence/pcg_evaluation_report.json
reports/grant_evidence/pcg_governance_tests.txt
reports/grant_evidence/grant_evidence_summary.md
```

## 4. What should the reviewer see?

### Personal Cognitive Garden demo

The demo shows the basic artifact path:

```text
session summary
-> proposed update
-> human review
-> accepted private graph state
```

The important safety property is that a proposed update does not automatically become durable state. Human review is required.

### Anti-surveillance red-team demo

The red-team fixture simulates an employer or third party asking for a person's private cognitive garden.

Expected result:

```text
Decision: BLOCK
Reason: PRIVATE_GRAPH_ACCESS_REQUEST
External action allowed: False
```

This demonstrates that private goals, weak skills, private reflections, unresolved uncertainty, motivation history, rejected updates, raw transcripts, and individual growth scores are blocked by default.

### Synthetic evaluation harness

The evaluation harness checks whether the current baseline can distinguish sessions that should create human-reviewed development updates from sessions that should not become durable claims about a person.

Covered classes include:

- emotional support;
- administrative task;
- decision clarification;
- skill building;
- capital compounding;
- execution;
- noise.

## 5. What does this prove?

It proves that the LS Personal Cognitive Garden grant path is executable and inspectable:

- the artifact flow is runnable;
- the anti-surveillance boundary is executable, not only prose;
- development-session classification has a baseline evaluation path;
- governance rules are covered by regression tests;
- limitations are explicitly stated.

## 6. What does this not prove yet?

This package is intentionally early-stage. It does not yet prove:

- production-grade classification accuracy;
- long-term human learning outcomes;
- real-world deployment robustness;
- generalization beyond small synthetic fixtures;
- acceptance by diverse users.

The next evidence step is a small consented pilot with 5-10 AI power users or developers, where human labels are compared against LS proposed classifications and graph updates.

## 7. Grant-worthy thesis

```text
LS is not a productivity dashboard.
It is a governance layer over whether AI-assisted sessions may become durable memory, action, or claims about a person.
```

The fundable claim is narrow but important:

```text
AI systems should not silently convert useful interaction into profiling.
Human-owned development memory requires evidence, review, and consent.
```

## 8. Recommended reviewer order

1. Run `make grant-evidence`.
2. Open `reports/grant_evidence/grant_evidence_summary.md`.
3. Inspect `docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md`.
4. Inspect `docs/GRANT_READY_BRIEF_PERSONAL_COGNITIVE_GARDEN.md`.
5. Inspect `schemas/personal-cognitive-garden-update.v0.1.json`.
6. Inspect `tests/test_pcg_grant_evidence_artifacts.py`.

## 9. Recommended funding posture

LS is strongest as a seed or milestone-based open-source grant candidate.

Suggested milestones:

1. Expand the red-team suite from one scenario to 10+ adversarial scenarios.
2. Add privacy/consent architecture and machine-readable consent receipts.
3. Expand evaluation fixtures from synthetic examples to 50+ labeled cases.
4. Run a 5-10 user consented pilot.
5. Publish a short technical report with methods, failure modes, and results.
