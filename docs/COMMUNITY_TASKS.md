# Community Task Board

This file is a public backlog for contributors. It is intentionally written in practical language so people can find a task without understanding the full LS architecture first.

Current focus:

> Personal Cognitive Garden: turn AI sessions into reviewed, evidence-backed, human-owned development updates without creating a surveillance layer.

Useful entry points:

- [Grant reviewer path](../GRANT.md)
- [Personal Cognitive Garden thesis](LS_PERSONAL_COGNITIVE_GARDEN.md)
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
