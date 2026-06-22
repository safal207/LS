# LS Public Roadmap

LS is moving toward three connected product lines:

```text
Personal Cognitive Garden
-> AI sessions become reviewed, human-owned development artifacts

Cooperative Precision Network
-> repeated AI co-work becomes more precise through route memory and contribution scoring

Trusted Cooperative Runtime
-> temporary multi-agent workflows become auditable, safely executable, replayable, and reusable cooperation artifacts
```

The precision thesis:

```text
LS does not make models smarter.
LS makes their cooperation more precise.
```

The runtime thesis:

```text
model output is a proposal
-> LS preserves task, route, evidence, and contribution
-> external trust modules validate cause, authorization, and execution
-> the result becomes a replayable reusable artifact
```

See:

- [Project Positioning](docs/PROJECT_POSITIONING.md)
- [Cooperative Precision Roadmap](docs/COOPERATIVE_PRECISION_ROADMAP.md)
- [Cooperative Role Market](docs/COOPERATIVE_ROLE_MARKET.md)
- [Trusted Cooperative Runtime MVP epic](https://github.com/safal207/LS/issues/599)

The Personal Cognitive Garden remains a local-first, human-owned development graph where AI sessions can become reviewed goals, skills, decisions, evidence, reflections, and growth paths.

The near-term Personal Cognitive Garden product line is:

```text
agent output
-> LS gateway review
-> proposed Personal Cognitive Garden update
-> human approval
-> durable growth graph
```

Agents may help cultivate the graph. The person owns it. Governance decides what becomes durable state.

## Trusted Cooperative Runtime MVP

LS is the coordinating product and provider-neutral integration runtime. Related repositories remain independent modules connected through adapters rather than copied into LS:

```text
LS workflow continuity
-> DAO_lim model/backend routing
-> CML causal-lineage audit
-> PythiaLabs evidence decision
-> ProofPath authorization bundle
-> CaPU commit-before-effect execution
-> LTP deterministic replay
-> LiminalDB event persistence
-> reusable LS artifact
```

The first product proof is a deterministic PR-review workflow built on the existing PR Review Trail Network.

### Phase 1 — Foundation

- [ ] [#591 Contracts, boundaries, and canonical schemas](https://github.com/safal207/LS/issues/591)
- [ ] [#592 Provider-neutral workflow orchestrator](https://github.com/safal207/LS/issues/592)

Exit condition: LS can create and validate a deterministic multi-role workflow with complete provider-neutral contracts.

### Phase 2 — Intelligence routing and trust

- [ ] [#593 Adapter registry and DAO_lim routing](https://github.com/safal207/LS/issues/593)
- [ ] [#594 CML causal audit and Cognitive Trail validation](https://github.com/safal207/LS/issues/594)
- [ ] [#595 Pythia evidence gates and ProofPath authorization bundles](https://github.com/safal207/LS/issues/595)

Exit condition: LS can explain which route was selected, why each action exists, and whether evidence and intent are sufficient.

### Phase 3 — Safe execution and continuity

- [ ] [#596 CaPU commit-before-effect execution control](https://github.com/safal207/LS/issues/596)
- [ ] [#597 LTP replay and LiminalDB event persistence](https://github.com/safal207/LS/issues/597)

Exit condition: protected side effects cannot occur before durable authorization, and workflows can be replayed or resumed.

### Phase 4 — Product proof

- [ ] [#598 End-to-end PR Review Trusted Runtime MVP](https://github.com/safal207/LS/issues/598)

Exit condition: one local command demonstrates `ALLOW`, `HOLD`, and `BLOCK` paths and exports a verified reusable PR-review artifact.

### Deferred until after the MVP

- Live cloud service, multi-tenant accounts, and billing.
- Production deployments, real payments, and destructive actions.
- Automatic writes to personal long-term memory.
- Full `osoznanie-ai` learning integration.
- Living Relational Identity integration.
- Performance claims against Fugu or frontier models.

Live landing page: https://safal207.github.io/LS/

## Now

- Start the Trusted Cooperative Runtime with [#591](https://github.com/safal207/LS/issues/591): stabilize contracts and failure semantics before live integrations.
- Make the Personal Cognitive Garden story clear in the README and landing page.
- Keep GitHub Pages deployment green from `ghostgpt-ls-landing`.
- Connect the LS Web Agent Gateway demo to the PCG story: review first, propose growth update second.
- Make the local PCG runner easy for reviewers to run and understand.
- Make PR-review trail artifacts easy to run and paste into pull requests.
- Clarify Cooperative Precision Network as a contributor-facing direction.
- Collect community feedback on wording, diagrams, onboarding, and anti-surveillance boundaries.

## Next

- Complete Trusted Runtime Phase 1 and begin the deterministic adapter registry.
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

- Complete the Trusted Runtime end-to-end PR-review product proof.
- Connect the landing page to live, sanitized runtime snapshots and PCG demo outputs.
- Split the product story into separate pages for safety, personal AI layer, PCG, runtime, and developer integration.
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
- Trusted Runtime: add schema fixtures, negative cases, adapter mocks, and deterministic replay examples.
- Role market: define how demand, design, execution, verification, and adoption become measurable artifacts.

If you want to help, start with an issue labeled `good first issue`, `landing`, `docs`, or `demo`.