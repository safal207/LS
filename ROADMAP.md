# LS Public Roadmap

LS is moving toward two connected product lines:

```text
Personal Cognitive Garden
-> AI sessions become reviewed, human-owned development artifacts

Cooperative Precision Network
-> repeated AI co-work becomes more precise through route memory and contribution scoring
```

The precision thesis:

```text
LS does not make models smarter.
LS makes their cooperation more precise.
```

See:

- [Project Positioning](docs/PROJECT_POSITIONING.md)
- [Cooperative Precision Roadmap](docs/COOPERATIVE_PRECISION_ROADMAP.md)
- [Cooperative Role Market](docs/COOPERATIVE_ROLE_MARKET.md)

The Personal Cognitive Garden remains a local-first, human-owned development graph where AI sessions can become reviewed goals, skills, decisions, evidence, reflections, and growth paths.

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
- Make PR-review trail artifacts easy to run and paste into pull requests.
- Clarify Cooperative Precision Network as a contributor-facing direction.
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
- Add contribution scoring to PR-review trail artifacts.
- Add role-market schema: customer, consumer, designer, executor, verifier, operator.
- Add fixtures and tests for cooperative precision signals.
- Add a Markdown benchmark report comparing single-reviewer and cooperative-review routes.

## Later

- Connect the landing page to live, sanitized runtime snapshots and PCG demo outputs.
- Split the product story into separate pages for safety, personal AI layer, PCG, and developer integration.
- Publish small public datasets of consented or synthetic PCG review traces.
- Add integrations for external agent tools through a documented LS gateway.
- Add consented export formats for portfolios, coaching, and aggregate-safe team views.
- Add GitHub Actions examples that publish LS review artifacts as CI outputs.
- Let external agents submit route artifacts through validation, trust boundaries, and decay.
- Match roles to tasks without turning role reputation into hidden people scoring.

## Community Tasks

Good first areas:

- PCG copy: explain "AI sessions should compound into human-owned development" in plain language.
- UI clarity: improve the gateway-to-garden flow, diagrams, button labels, and mobile layout.
- Docs: shorten setup paths and add reviewer scripts.
- Tests: add focused checks for landing build, runtime fallback, gateway contracts, and PCG runner output.
- Examples: create realistic before/after agent-output and PCG update cases.
- Cooperative precision: improve PR-review trail signals, contribution scoring, and benchmark reports.
- Role market: define how demand, design, execution, verification, and adoption become measurable artifacts.

If you want to help, start with an issue labeled `good first issue`, `landing`, `docs`, or `demo`.
