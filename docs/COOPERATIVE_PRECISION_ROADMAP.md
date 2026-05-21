# Cooperative Precision Network Roadmap

LS is growing a cooperative precision layer for AI co-work.

Canonical project positioning:

- [Project Positioning](PROJECT_POSITIONING.md)
- [Cooperative Role Market](COOPERATIVE_ROLE_MARKET.md)

The thesis is deliberately narrow:

```text
LS does not make models smarter.
LS makes their cooperation more precise.
```

Every repeated process can leave a route artifact:

```text
task
-> cooperative route
-> verified contribution
-> evidence
-> reward or penalty
-> better route choice next time
```

This is a Nash-style repeated cooperative game, not a claim that LS proves Nash
equilibrium. The practical goal is simpler: make it more rewarding for agents
and contributors to produce verified value than to produce noisy output.

## Why Contributors Should Care

Most AI systems compare model outputs as isolated answers. LS measures the
process that produced the answer:

- Which route worked?
- Which role found the real risk?
- Which contribution had evidence?
- Which route reduced uncertainty?
- Which route should be reused next time?
- Which role should be matched to the next similar task?

This creates a thin but useful benchmark for cooperative AI work:

```text
not "which model is best?"
but "which cooperation pattern produces verified value?"
```

## Product Wedge

The first narrow use case is:

```text
AI Code Review / PR Review Trail Network
```

Why this first:

- Git diffs are concrete evidence.
- CI gives external signals.
- Human review comments can validate or reject findings.
- Routes are easy to compare.
- Contributors already understand pull-request review.

Current commands:

```bash
python scripts/run_pr_review_trail_demo.py
python scripts/run_pr_review_trail_artifact.py
python scripts/run_role_market_demo.py
python scripts/run_pr_role_market_demo.py
```

## Phase 0: Local Trail Artifacts

Goal: make every PR review produce a portable artifact.

Already started:

- Route selection demo.
- Real git diff artifact builder.
- Route reward update.
- Markdown and JSON output.

Contributor tasks:

- Improve review signal detection for common risky changes.
- Add fixtures with small safe and risky diffs.
- Add tests for `scripts/run_pr_review_trail_artifact.py`.
- Make the Markdown artifact easier to paste into a PR.
- Add examples under `examples/pr_review_trails/`.

Definition of done:

```text
one command -> real diff -> review artifact -> route reward
```

## Phase 1: Contribution Ledger

Goal: measure who contributed value inside the route.

Example route:

```text
draft_reviewer
-> risk_critic
-> evidence_verifier
-> final_reviewer
```

Contributor tasks:

- Add `contributors` to PR review artifacts.
- Assign contribution scores by role.
- Separate true findings from false positives.
- Add penalties for unsupported claims.
- Add role-specific summaries:
  - best critic
  - best verifier
  - best final summarizer

Possible scoring shape:

```text
contribution_score =
  accepted_findings
+ evidence_quality
+ risk_reduction
+ goal_alignment
- false_positives
- unsupported_claims
```

Definition of done:

```text
route reward explains both the route and the contributors inside it
```

## Phase 2: Cooperative Benchmark

Goal: compare routes, not just models.

Baseline:

```text
single reviewer
```

Cooperative route:

```text
draft -> critic -> verifier -> final
```

Contributor tasks:

- Add benchmark fixtures for PR review.
- Compare single-model and cooperative routes.
- Track precision, false positives, missing tests, and evidence quality.
- Add a small leaderboard by route and role.
- Render a benchmark report in Markdown.

Definition of done:

```text
contributors can run a benchmark and see which route is more precise
```

## Phase 3: GitHub Workflow Integration

Goal: attach LS review artifacts to real GitHub work.

Contributor tasks:

- Add a GitHub Actions example that runs the artifact builder.
- Upload JSON/Markdown artifacts from CI.
- Add safe defaults for forks and public PRs.
- Keep the system advisory-only by default.
- Document how maintainers can use the artifact during review.

Definition of done:

```text
pull request -> LS artifact -> reviewer sees route, signals, and contribution trace
```

## Phase 4: Cooperative Role Market

Goal: match the right role to the right work.

Role chain:

```text
customer -> consumer -> designer -> executor -> verifier -> operator
```

Contributor tasks:

- Add role fields to PR review artifacts.
- Add a role-output schema for draft reviewer, critic, verifier, and final reviewer.
- Score verified value by role.
- Track best role-specific contributors without turning it into general identity scoring.
- Add examples where the designer improves the route even if another actor executes it.

Definition of done:

```text
LS can explain which role contributed value and which role should be matched next time
```

## Phase 5: Open Cooperative Network

Goal: let external agents submit route outcomes without giving them authority.

Contributor tasks:

- Define route artifact schema.
- Add validation for external route submissions.
- Add trust boundaries for unknown agents.
- Add decay for weak or stale routes.
- Add privacy rules for personal or organization-specific routes.

Definition of done:

```text
external agents can contribute evidence, but LS decides what becomes trusted route memory
```

## Good First Issues

Small tasks that help immediately:

- Add three tiny PR diff fixtures:
  - docs-only change
  - code change without tests
  - risky shell command change
- Add a unit test for missing-test detection.
- Improve the Markdown artifact wording.
- Add a README screenshot or sample output block.
- Add a short "What is route reward?" explanation.
- Add a `--no-diff-excerpt` flag for smaller JSON artifacts.
- Add examples of false positive and true positive review signals.

Suggested labels:

```text
good first issue
cooperative-precision
pr-review
trail-network
benchmark
contribution-ledger
```

## Guardrails

This roadmap should avoid overclaiming.

LS should not say:

```text
the network becomes generally smarter
```

LS should say:

```text
the network becomes more precise at repeated, evidence-backed cooperation
```

LS should not say:

```text
we solved AI safety
```

LS should say:

```text
we add one auditable primitive: verified cooperative route memory
```

## North Star

```text
Continuity before continuation.
Evidence before action.
Consent before memory.
Contribution before reputation.
Precision before scale.
```
