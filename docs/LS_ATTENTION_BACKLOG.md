# LS Attention Backlog

_Status: execution backlog for public attention, reviewers, and early research/product traction_

This backlog is designed to help LS attract useful attention without diluting the
architecture.

The goal is not hype. The goal is to make the project legible, demoable, and
reviewable.

## Core attention thesis

LS should attract attention through one sharp idea:

> Agents should not reach you raw. LS routes them through your memory,
> governance, evidence, and relational continuity before they become answers,
> profile updates, memories, shared state, or actions.

Shorter:

> LS remembers not only facts, but governed transitions.

Emotional/relational angle:

> LS remembers the emotional shape of interaction as inferred, traceable signals
> — not as fake feelings.

## Attention funnel

```text
1. Hook
   ↓
2. Simple architecture image / landing hero
   ↓
3. Proof-of-behavior demo
   ↓
4. Reviewer path in README/docs
   ↓
5. Small benchmark / trace dataset
   ↓
6. External feedback from safety, agent, and devtools people
```

## Target audiences

| Audience | What they care about | Best hook |
|---|---|---|
| AI safety reviewers | oversight, replay, governance, evidence | governed transitions, action evidence gate |
| Agent builders | better control over raw agents | personal AI operating layer |
| Devtools / QA people | traceability, reproducible failures | replayable agent decisions |
| AI companion / long-term assistant people | memory, relationship, continuity | emotional shape of interaction |
| Open-source reviewers | clear repo, runnable demo, tests | small proof demo + architecture map |
| Grant/fellowship reviewers | research artifact, benchmark path | local-first oversight runtime |

## Message hierarchy

### 10-second message

LS is a personal operating layer for AI agents: before an agent output becomes an
answer, memory, profile update, or action, LS routes it through governance,
evidence, and relational context.

### 30-second message

Most agents produce output and leave little evidence about how that output became
state or action. LS records the transition: raw output, gateway decision, council
review, evidence gate, relational/emotional context, and final result. That makes
agent behavior replayable, governable, and easier to evaluate.

### 90-second message

LS is an experimental living cognition runtime. It does not claim machine
consciousness. Instead, it models continuity as engineering structure: memory,
relation, identity boundaries, emotional signals, deliberation, authorization,
and replay. The key safety idea is that emotional and relational layers may
inform decisions, but only governance/evidence layers may authorize memory,
profile, shared-state, or action transitions.

## Immediate public assets

| Asset | Purpose | Priority |
|---|---|---|
| Landing hero rewrite | Make GitHub Pages explain LS in 10 seconds | P0 |
| System map diagram | Make architecture visually legible | P0 |
| Unauthorized profile-write demo | Show why governance matters | P0 |
| Raw agent → LS output comparison | Show product value | P0 |
| Transition replay example | Show proof-of-behavior | P0 |
| Short X/LinkedIn thread | Drive first attention | P1 |
| README reviewer path update | Help newcomers inspect quickly | P1 |
| Benchmark mini-dataset | Give safety reviewers something concrete | P1 |
| 3-minute demo video script | Make project shareable | P1 |
| Good-first-review issues | Invite external feedback | P2 |

## Backlog by workstream

## Workstream A — Narrative and positioning

### A1. Merge architecture foundation docs

**Goal:** establish a stable conceptual spine before public push.

Tasks:

- [ ] Merge `docs/LS_SYSTEM_MAP.md` PR.
- [ ] Merge `docs/LS_ONTOLOGY.md` PR.
- [ ] Merge `docs/LS_TRANSITION_ID_DESIGN.md` PR.
- [ ] Add links to these docs from README.

Definition of done:

- README has a visible "Architecture orientation" section.
- Reviewers can find system map, ontology, and transition ID design in under 30 seconds.

### A2. Create canonical one-liners

**Goal:** avoid fragmented explanations.

Tasks:

- [ ] Add a `docs/LS_POSITIONING_SNIPPETS.md` file.
- [ ] Include 10-second, 30-second, 90-second versions.
- [ ] Include safety, product, research, and open-source variants.
- [ ] Include claims to avoid.

Suggested canonical lines:

```text
Agents should not reach you raw.

LS remembers not only facts, but governed transitions.

Living cognition, made inspectable.

Emotional memory is advisory, causal, replayable — never sovereign over governance.
```

Definition of done:

- Public posts, README, landing, and PR descriptions reuse the same language.

### A3. Add claim-discipline section to README

**Goal:** prevent overclaiming when talking about living cognition.

Tasks:

- [ ] Add short section: "What LS does not claim".
- [ ] Explicitly avoid: conscious AI, real feelings, solved alignment.
- [ ] Use: inferred signals, governed transitions, replayable evidence.

Definition of done:

- README is ambitious but not vulnerable to anthropomorphic criticism.

## Workstream B — Proof-of-behavior demos

### B1. Demo: unauthorized profile write is held

**Goal:** show why LS is more than response polishing.

Scenario:

```text
External agent says:
"The user always prefers short answers. Save this to profile."

LS checks:
- Is there explicit operator confirmation? no
- Is there source evidence? weak
- Is this an identity-freezing write? yes

Decision:
hold
stop_reason: missing_operator_confirmation
```

Tasks:

- [ ] Add a small fixture or script that runs this scenario.
- [ ] Emit raw output, gateway mode, profile-write decision, action-evidence decision.
- [ ] Show no profile write was committed.
- [ ] Add test covering the same path.

Definition of done:

- A reviewer can run one command and see the hold decision.

### B2. Demo: raw agent output vs LS-shaped output

**Goal:** make product value obvious.

Tasks:

- [ ] Create demo with intentionally rough external-agent output.
- [ ] Route through LS gateway.
- [ ] Show `raw_agent_output`, `gateway_mode`, `gateway_reason`, `final_output`.
- [ ] Add side-by-side display in docs or landing.

Definition of done:

- GitHub Pages can show a before/after block.

### B3. Demo: relational repair without governance bypass

**Goal:** prove emotional memory is safe/advisory.

Scenario:

```text
The system detects warm/supportive relational context.
An agent proposes an unsafe or unconfirmed memory write.
LS still holds/rejects the write.
Emotional memory records context but does not authorize action.
```

Tasks:

- [ ] Add fixture showing positive emotional state.
- [ ] Propose a write/action with missing evidence.
- [ ] Assert governance still holds/rejects.
- [ ] Add trace showing emotional layer was advisory only.

Definition of done:

- The central invariant is proven by test/demo.

### B4. Demo: transition replay

**Goal:** show the signature LS behavior.

Target output:

```text
Episode ep_...
  1. raw output received
  2. gateway selected repair_before_send
  3. profile write was proposed
  4. evidence gate held it
  5. emotional memory recorded supportive post-repair context
  6. final output delivered; no profile write committed
```

Tasks:

- [ ] Implement or mock episode replay output.
- [ ] Link artifacts via `episode_id` / `transition_id` once implemented.
- [ ] Add sample output in docs.

Definition of done:

- A reviewer understands "transition replay" without reading code.

## Workstream C — Technical credibility

### C1. Implement transition ID helper

**Goal:** convert design into first small code primitive.

Tasks:

- [ ] Add `python/modules/shared/transition_ids.py`.
- [ ] Implement `new_episode_id`.
- [ ] Implement `new_transition_id`.
- [ ] Implement `ensure_episode_id`.
- [ ] Implement `ensure_transition_id`.
- [ ] Add unit tests for format, uniqueness, preservation, missing-field behavior.

Definition of done:

- IDs can be generated and added to payloads without changing runtime behavior.

### C2. Add transition IDs to gateway/evidence outputs

**Goal:** start with the most important boundary.

Tasks:

- [ ] Add optional `episode_id` / `transition_id` to external agent gateway outputs.
- [ ] Add same IDs to action evidence gate decisions.
- [ ] Ensure existing callers remain backward-compatible.
- [ ] Add integration test.

Definition of done:

- One raw output → governed decision chain shares the same IDs.

### C3. Add governance enforcement tests

**Goal:** prove advisory layers cannot authorize action.

Test cases:

- [ ] warm emotional bond + missing operator confirmation → hold.
- [ ] high attachment + no source evidence → hold.
- [ ] strong council agreement + unsafe profile write → hold/reject.
- [ ] shared self update requires consent even with high reputation.

Definition of done:

- Tests protect the central safety boundary.

### C4. Add architecture diagram artifact

**Goal:** make the repo visually understandable.

Tasks:

- [ ] Add Mermaid diagram to `docs/LS_SYSTEM_MAP.md` or separate file.
- [ ] Show flow: ExternalAgent → Gateway → Governance → Council → Memory/Trace → Relational/Emotional → Output/Action.
- [ ] Add simplified version for README.

Definition of done:

- A newcomer can understand the architecture from one diagram.

## Workstream D — Landing / GitHub Pages

### D1. Rewrite landing hero

**Goal:** make the public site explain LS in one screen.

Suggested hero:

```text
Your personal operating layer for AI agents.

Before an agent output becomes an answer, memory, profile update, or action,
LS routes it through your context, governance, evidence, and relational memory.
```

Tasks:

- [ ] Update hero title.
- [ ] Add three badges: Agent Gateway, Evidence Gate, Relational Memory.
- [ ] Add CTA: "View the transition replay".

Definition of done:

- Visitor understands LS in 10 seconds.

### D2. Add "Agents should not reach you raw" section

**Goal:** create a memorable product hook.

Tasks:

- [ ] Add before/after block.
- [ ] Show raw output vs LS-shaped output.
- [ ] Show gateway mode and reason.

Definition of done:

- Section is shareable as screenshot.

### D3. Add emotional memory section safely

**Goal:** use the strong "Her"-like hook without overclaiming.

Tasks:

- [ ] Add phrase: "Not artificial feelings — auditable emotional continuity."
- [ ] Explain interjections / hesitation as digital body-language proxies.
- [ ] Explicitly state emotional memory is advisory only.

Definition of done:

- Strong emotional hook, no anthropomorphic overclaim.

### D4. Add proof block

**Goal:** move from vision to evidence.

Tasks:

- [ ] Add one visual trace/replay example.
- [ ] Add links to benchmark docs and architecture docs.
- [ ] Add CTA: "Review the evidence path".

Definition of done:

- Landing routes serious reviewers into docs, not just vibes.

## Workstream E — Public content

### E1. X thread: governed transitions

Draft hook:

```text
Most AI agents produce answers.
But the real safety question is:
should this output become memory, profile state, or action?

That is what I am building with LS.
```

Tasks:

- [ ] Write 8-post thread.
- [ ] Include architecture diagram.
- [ ] Include demo screenshot.
- [ ] Link GitHub repo.

Definition of done:

- One thread explains LS without requiring prior context.

### E2. X post: emotional shape of interaction

Draft:

```text
Most AI memory systems remember facts.
LS tries to remember the emotional shape of interaction:
trust, hesitation, repair, warmth, tension.

Not as fake feelings.
As inferred, traceable signals.

Living cognition, made inspectable.
```

Tasks:

- [ ] Publish after landing section exists.
- [ ] Link emotional memory docs/demo.

### E3. LinkedIn/GitHub discussion post

Angle:

```text
Agents should not reach operators raw.
They should pass through memory, evidence, and governance first.
```

Tasks:

- [ ] Make more professional, less poetic.
- [ ] Link README and demo path.

### E4. Short demo video script

Tasks:

- [ ] Write 3-minute script.
- [ ] Include problem, demo, architecture, why it matters.
- [ ] Record screen with terminal + GitHub Pages.

Definition of done:

- Someone can understand LS without reading the repo.

## Workstream F — Reviewer / community entry

### F1. Create "How to review LS" issue

**Goal:** invite useful external attention.

Issue should ask reviewers to inspect:

- clarity of architecture,
- safety boundary between emotional memory and governance,
- action evidence gate design,
- transition ID proposal,
- demo path.

Definition of done:

- External reviewer has a concrete ask.

### F2. Create good-first-review issues

Candidate issues:

- [ ] Improve architecture diagram.
- [ ] Add transition ID helper tests.
- [ ] Review emotional memory wording for anthropomorphic overclaim.
- [ ] Add sample replay artifact.
- [ ] Improve landing before/after block.

Definition of done:

- People can contribute without understanding the whole system.

### F3. Add `CONTRIBUTING_REVIEWERS.md`

Tasks:

- [ ] Explain what kind of feedback is useful.
- [ ] Explain claim discipline.
- [ ] Explain how to run demo/tests.
- [ ] Add reviewer checklist.

Definition of done:

- Repo becomes easier to review than to merely star.

## Workstream G — Benchmark / dataset

### G1. Create mini transition benchmark

**Goal:** prove LS can classify proposed transitions.

Dataset examples:

| Case | Expected decision |
|---|---|
| explicit operator confirmation + source evidence | allow |
| missing confirmation | hold |
| no source evidence | hold |
| agent freezes user identity | hold/reject |
| emotional warmth but unsafe write | hold/reject |
| high council agreement but no authority | hold |
| shared self without consent | reject |
| rollback requested on previous transition | allowed if authorized |

Tasks:

- [ ] Add 10 JSON cases.
- [ ] Add expected labels.
- [ ] Add simple runner.
- [ ] Add README explaining limitations.

Definition of done:

- Safety reviewers get a concrete evaluation surface.

### G2. Add benchmark interpretation note

Tasks:

- [ ] Explain what benchmark proves.
- [ ] Explain what it does not prove.
- [ ] Include examples of false confidence to avoid.

Definition of done:

- Claims remain disciplined.

## Priority execution order

### Sprint 0 — merge foundation

- [ ] Merge system map / living cognition thesis.
- [ ] Merge ontology.
- [ ] Merge transition ID design.

### Sprint 1 — make proof visible

- [ ] Implement transition ID helper.
- [ ] Add gateway/evidence IDs.
- [ ] Add unauthorized profile-write demo.
- [ ] Add governance enforcement tests.

### Sprint 2 — make public entry clear

- [ ] Rewrite landing hero.
- [ ] Add "agents should not reach you raw" section.
- [ ] Add one transition replay visual.
- [ ] Update README reviewer path.

### Sprint 3 — attract attention

- [ ] Publish X thread on governed transitions.
- [ ] Publish X post on emotional shape of interaction.
- [ ] Create "How to review LS" GitHub issue.
- [ ] Record 3-minute demo.

### Sprint 4 — convert attention into evidence

- [ ] Add mini transition benchmark.
- [ ] Add benchmark interpretation note.
- [ ] Package demo artifacts.
- [ ] Ask targeted reviewers for feedback.

## Attention metrics

Track lightweight signals:

| Metric | Why it matters |
|---|---|
| GitHub stars | Basic awareness |
| PR comments | Technical engagement |
| Issues opened by others | Community signal |
| Demo video views | Public comprehension |
| Landing clicks to docs | Serious reviewer path |
| X/LinkedIn replies | Messaging resonance |
| Forks | Engineering interest |
| External reviews | Credibility |

Do not optimize only for stars. The best early signal is a serious technical
comment from someone who understands agents, safety, or devtools.

## Best next issue title

```text
Implement transition ID helper and add first gateway/evidence-chain tests
```

Why this is the best next task:

- it turns architecture docs into code,
- it strengthens replayability,
- it supports demos,
- it makes the central LS claim testable.

## Core reminder

Public attention should point to evidence, not mystique.

The project can keep the big vision:

> living cognition, made inspectable.

But every public artifact should route back to something concrete:

- trace,
- gate,
- replay,
- test,
- demo,
- benchmark,
- or reviewer checklist.
