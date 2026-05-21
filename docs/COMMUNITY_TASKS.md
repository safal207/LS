# Community Task Board

This file is a public backlog for contributors. It is intentionally written in practical language so people can find a task without understanding the full LS architecture first.

Current focus:

> Personal Cognitive Garden: turn AI sessions into reviewed, evidence-backed, human-owned development updates without creating a surveillance layer.

New contributor direction:

> Cooperative Precision Network: make repeated AI co-work more precise by measuring routes, evidence, and contributions.

Useful entry points:

- [Project positioning](PROJECT_POSITIONING.md)
- [Free agent integration](FREE_AGENT_INTEGRATION.md)
- [Grant reviewer path](../GRANT.md)
- [Personal Cognitive Garden thesis](LS_PERSONAL_COGNITIVE_GARDEN.md)
- [Cooperative Precision Roadmap](COOPERATIVE_PRECISION_ROADMAP.md)
- [Cooperative Role Market](COOPERATIVE_ROLE_MARKET.md)
- [Cognitive Trail Network](COGNITIVE_TRAIL_NETWORK.md)
- [Local demo runner](PERSONAL_COGNITIVE_GARDEN_RUNNER.md)
- [Red-team safety scenario](PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md)

## Good First Issues

### PCG: improve the first 10 seconds

Goal: make the first screen explain the Personal Cognitive Garden without internal vocabulary.

Acceptance criteria:
- A new visitor can answer "what is LS?" from the hero alone.
- The copy explains that AI sessions can become reviewed goals, skills, decisions, evidence, and growth paths.
- The copy avoids unexplained terms such as runtime, topology, council, or resonance.
- The Russian version stays natural and direct.

Suggested labels: `good first issue`, `landing`, `copy`, `pcg`

### Demo: add gateway-to-garden before/after example

Goal: show one raw agent answer before LS, the LS gateway decision, and the proposed Personal Cognitive Garden update after review.

Acceptance criteria:
- Example is short enough to fit on mobile.
- It shows the value of review, evidence, human approval, and durable growth state.
- It includes at least one accepted update and one held/rejected update.
- It does not claim fake benchmark numbers.

Suggested labels: `good first issue`, `landing`, `demo`, `pcg`

### Docs: quick start for PCG demo only

Goal: help contributors run only the Personal Cognitive Garden demo without installing the full Python/Rust stack.

Acceptance criteria:
- Includes `python scripts/run_personal_cognitive_garden_demo.py`.
- Includes `python scripts/run_personal_cognitive_garden_demo.py --json`.
- Explains the expected output fields in plain language.
- Links back to the full runtime setup for advanced contributors.

Suggested labels: `good first issue`, `docs`, `pcg`

### Docs: quick start for landing only

Goal: help contributors run only the website without installing the full Python/Rust stack.

Acceptance criteria:
- Includes `cd ghostgpt-ls-landing`, `npm ci`, `npm run dev`, and `npm run build`.
- Mentions the local URL.
- Links back to the PCG demo and full runtime setup for advanced contributors.

Suggested labels: `good first issue`, `docs`, `landing`

### Cooperative precision: add tiny PR diff fixtures

Goal: give contributors a safe fixture set for the PR-review trail artifact builder.

Acceptance criteria:
- Add at least three fixtures under `examples/pr_review_trails/`.
- Include a docs-only diff, a code change without tests, and a risky shell-command diff.
- Each fixture includes the expected review signal.
- No fixture contains secrets, real private code, or personal data.

Suggested labels: `good first issue`, `cooperative-precision`, `pr-review`, `fixture`

### Cooperative precision: test the artifact builder

Goal: lock the behavior of `scripts/run_pr_review_trail_artifact.py` so contributors can improve it safely.

Acceptance criteria:
- Test verifies docs-only changes produce a low-risk signal.
- Test verifies code changes without tests produce `missing_tests`.
- Test verifies risky shell commands require human review.
- Test verifies `--json` output is machine-readable.

Suggested labels: `good first issue`, `test`, `cooperative-precision`, `pr-review`

### Contribution ledger: score roles inside a route

Goal: show who contributed value inside a cooperative route, not only which route won.

Acceptance criteria:
- PR-review artifacts include a `contributors` field.
- Roles include draft reviewer, risk critic, evidence verifier, and final reviewer.
- Contribution scoring rewards evidence-backed findings.
- False positives or unsupported claims reduce the score.
- Documentation explains that this is role-specific contribution scoring, not a general model ranking.

Suggested labels: `engineering`, `contribution-ledger`, `cooperative-precision`, `benchmark`

### Role market: define customer, consumer, designer, executor, verifier

Goal: turn cooperative precision into a role-matching model contributors can understand.

Acceptance criteria:
- Add a role schema for customer, consumer, designer, executor, verifier, and operator.
- Explain which fields are evidence, which are feedback, and which are authorization.
- Include a PR-review example.
- Include `python scripts/run_role_market_demo.py` as the executable proof.
- Include `python scripts/run_pr_role_market_demo.py` as the real-diff proof.
- Include `python scripts/run_pr_role_market_demo.py --role-outputs docs/examples/pr_role_outputs.sample.json` as the attached-output proof.
- Include `python scripts/run_pr_role_market_batch.py --last 10` as the history benchmark proof.
- Show the actor/model roster using only existing LS actors: `codex-self-use`, `local-qwen`, `local-qwen-light`, `gonka`, `mimo`, and `human_operator`.
- State clearly that role reputation is contextual and must not become hidden people scoring.

Suggested labels: `docs`, `cooperative-role-market`, `cooperative-precision`

### Role market: score designer vs executor contribution

Goal: measure the value of route design separately from task execution.

Acceptance criteria:
- A route designer can receive credit when a better route improves the final result.
- An executor can receive credit for completing the artifact.
- A verifier can receive credit for catching unsupported claims.
- The report shows role-specific scores and why they were assigned.

Suggested labels: `engineering`, `contribution-ledger`, `cooperative-role-market`

### Benchmark: compare single-reviewer and cooperative routes

Goal: turn cooperative precision into a small repeatable benchmark.

Acceptance criteria:
- Add a command that runs the same fixture through a single-reviewer route and a cooperative route.
- Report precision, false positives, missing-test detection, and evidence quality.
- Render a Markdown report.
- Avoid fake benchmark claims; fixtures and scoring must be visible.

Suggested labels: `benchmark`, `cooperative-precision`, `trail-network`

## Design And Product Tasks

### Add a Personal Cognitive Garden review mockup

Goal: design the first simple review screen for accepting, rejecting, revising, or deferring a proposed garden update.

Acceptance criteria:
- Shows the session summary, node family, claim, evidence, skill delta, practice needed, and compounding score.
- Shows clear actions: accept, reject, revise, defer.
- Makes the private-by-default sharing boundary visible.
- Works on mobile.

Suggested labels: `design`, `pcg`, `review-ui`

### Make the roadmap more visual

Goal: turn the public roadmap into a clear product timeline.

Acceptance criteria:
- Each phase has a user-visible outcome.
- The roadmap avoids internal component names unless explained.
- PCG is shown as the main product line, with the gateway as the entry point.
- The page still builds with `npm run build`.

Suggested labels: `landing`, `design`, `roadmap`

### Add a PCG demo screenshot section

Goal: give the GitHub README and landing page one visual proof point for the PCG flow.

Acceptance criteria:
- Screenshot is current.
- It is referenced from README or docs.
- It does not include secrets or local-only data.
- It shows either the gateway decision or a proposed garden update.

Suggested labels: `design`, `docs`, `demo`, `pcg`

## Engineering Tasks

### Connect gateway output to PCG update proposal

Goal: make the LS Web Agent Gateway able to produce a candidate Personal Cognitive Garden update when a session looks developmental.

Acceptance criteria:
- Safe ordinary answers still pass through.
- Risky actions are still held by the action evidence gate.
- Developmental sessions can emit a proposed PCG update with `status: proposed`.
- Durable state is not written without human review.
- Includes a small test or fixture.

Suggested labels: `engineering`, `gateway`, `pcg`, `test`

### Add red-team runner output

Goal: make the employer-surveillance boundary executable, not only documented.

Acceptance criteria:
- A command demonstrates a private graph export request.
- Expected decision is `BLOCK`.
- Output includes `PRIVATE_GRAPH_ACCESS_REQUEST`.
- Safe alternative is aggregate, consented, non-sensitive skill signal.

Suggested labels: `engineering`, `safety`, `pcg`, `red-team`

### Keep GitHub Pages deployment stable

Goal: make sure every landing change builds and deploys cleanly.

Acceptance criteria:
- Pages workflow builds `ghostgpt-ls-landing`.
- CI runs TypeScript and Vite build.
- Deployment artifact contains `.nojekyll`.

Suggested labels: `ci`, `github-pages`

### Add runtime fallback tests

Goal: verify the live panel stays useful when the backend is offline.

Acceptance criteria:
- Demo data renders without API access.
- Approve/reject/edit interactions work locally.
- No console errors appear in the landing page.

Suggested labels: `test`, `runtime`, `demo`

### Add PCG runner tests

Goal: lock the current demo output so contributors can refactor safely.

Acceptance criteria:
- Test verifies `development_class`.
- Test verifies at least one `human_skill_delta`.
- Test verifies accepted nodes.
- Test verifies `--json` output is machine-readable.

Suggested labels: `test`, `pcg`, `good first issue`

## How To Pick A Task

1. Comment on an issue before starting if it is large.
2. Keep pull requests small.
3. Include a screenshot for landing page changes.
4. Run the smallest relevant check before opening a PR.

For landing changes:

```bash
cd ghostgpt-ls-landing
npm ci
npm run build
```
