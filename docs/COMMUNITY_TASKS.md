# Community Task Board

This file is a public backlog for contributors. It is intentionally written in practical language so people can find a task without understanding the full LS architecture first.

## Good First Issues

### Landing: improve the first 10 seconds

Goal: make the first screen explain LS without internal vocabulary.

Acceptance criteria:
- A new visitor can answer "what is LS?" from the hero alone.
- The copy avoids unexplained terms such as runtime, topology, council, or resonance.
- The Russian version stays natural and direct.

Suggested labels: `good first issue`, `landing`, `copy`

### Landing: add before/after example

Goal: show one weak agent answer before LS and one improved answer after LS.

Acceptance criteria:
- Example is short enough to fit on mobile.
- It shows the value of memory, review, or approval.
- It does not claim fake benchmark numbers.

Suggested labels: `good first issue`, `landing`, `demo`

### Docs: quick start for landing only

Goal: help contributors run only the website without installing the full Python/Rust stack.

Acceptance criteria:
- Includes `cd ghostgpt-ls-landing`, `npm ci`, `npm run dev`, and `npm run build`.
- Mentions the local URL.
- Links back to the full runtime setup for advanced contributors.

Suggested labels: `good first issue`, `docs`

## Design And Product Tasks

### Make the roadmap more visual

Goal: turn the public roadmap into a clear product timeline.

Acceptance criteria:
- Each phase has a user-visible outcome.
- The roadmap avoids internal component names unless explained.
- The page still builds with `npm run build`.

Suggested labels: `landing`, `design`, `roadmap`

### Add a demo screenshot section

Goal: give the GitHub README and landing page one visual proof point.

Acceptance criteria:
- Screenshot is current.
- It is referenced from README or docs.
- It does not include secrets or local-only data.

Suggested labels: `design`, `docs`, `demo`

## Engineering Tasks

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
