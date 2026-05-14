# LS Public Roadmap

LS is moving toward a Personal Cognitive Garden: a local-first, human-owned development graph where AI sessions can become reviewed goals, skills, decisions, evidence, reflections, and growth paths.

The near-term product line is:

```text
agent output
-> LS gateway review
-> proposed Personal Cognitive Garden update
-> human approval
-> durable growth graph
```

Agents may help cultivate the graph. The person owns it. Governance decides what becomes durable state.

Live landing page: https://safal207.github.io/LS/

## Now

- Make the Personal Cognitive Garden story clear in the README and landing page.
- Keep GitHub Pages deployment green from `ghostgpt-ls-landing`.
- Connect the LS Web Agent Gateway demo to the PCG story: review first, propose growth update second.
- Make the local PCG runner easy for reviewers to run and understand.
- Collect community feedback on wording, diagrams, onboarding, and anti-surveillance boundaries.

## Next

- Add a PCG review UI: proposed update, evidence, accept/reject/defer.
- Add a red-team demo runner for employer private-graph access requests.
- Publish minimal before/after examples:
  - raw agent output before LS;
  - LS gateway decision;
  - proposed PCG update;
  - accepted graph state.
- Add more replayable PCG examples under `examples/personal_cognitive_garden/`.
- Improve local setup docs for contributors who only want to run the landing page or the PCG demo.
- Add screenshots and expected outcomes to issues that are ready for design help.

## Later

- Connect the landing page to live, sanitized runtime snapshots and PCG demo outputs.
- Split the product story into separate pages for safety, personal AI layer, PCG, and developer integration.
- Publish small public datasets of consented or synthetic PCG review traces.
- Add integrations for external agent tools through a documented LS gateway.
- Add consented export formats for portfolios, coaching, and aggregate-safe team views.

## Community Tasks

Good first areas:

- PCG copy: explain "AI sessions should compound into human-owned development" in plain language.
- UI clarity: improve the gateway-to-garden flow, diagrams, button labels, and mobile layout.
- Docs: shorten setup paths and add reviewer scripts.
- Tests: add focused checks for landing build, runtime fallback, gateway contracts, and PCG runner output.
- Examples: create realistic before/after agent-output and PCG update cases.

If you want to help, start with an issue labeled `good first issue`, `landing`, `docs`, or `demo`.
