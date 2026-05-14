# Target Audience and Outreach Map

## Purpose

This document translates LS into concrete audiences, buyer pains, pitches, offers, and next actions.

It answers:

```text
Who has this pain?
Why would they care now?
What should we show them?
What should we not sell?
What is the smallest paid or funded step?
```

## Core positioning

Short version:

```text
LS is continuity infrastructure for human-agent work.
```

Operational version:

```text
LS detects broken session continuity, restores the last shared orientation point, and requires evidence before memory or action.
```

Safety version:

```text
LS detects hallucinated continuation before it becomes action, memory, or evaluation.
```

Human-development version:

```text
LS turns AI sessions into governed, human-owned skill capital without becoming employee surveillance.
```

## Core thesis

```text
Continuity before continuation.
Evidence before action.
Consent before memory.
Repair before judgment.
```

## Expensive pain

AI work is becoming multi-agent and multi-session:

```text
Claude
+ Codex
+ Cursor
+ ChatGPT
+ IDE agents
+ browser agents
+ PRs
+ tickets
+ voice notes
+ docs
+ Slack threads
```

The failure mode:

```text
context breaks
-> agent fills the gap
-> human fills the gap
-> work continues from invented continuity
-> wrong code, wrong action, wrong memory, wrong evaluation, or broken trust
```

The LS intervention:

```text
detect rupture
-> restore last shared point
-> repair before continuation
-> require evidence before memory/action
-> preserve reviewable trace
```

## Priority audiences

### P0 — AI safety / governance grant reviewers

Why they care:

- LS is not another chatbot.
- It is an oversight runtime for continuity, consent, repair, and evidence.
- It addresses hallucinated continuation, missing context, unsupported memory, and unreviewed action.

Pain:

```text
How do we know an AI-agent action or memory update followed a valid, reviewable, human-governed path?
```

Pitch:

```text
LS provides local-first artifacts for detecting broken continuity and preventing unsupported continuation before it becomes action or memory.
```

Show:

- `GRANT.md`
- `docs/GRANT_READY_BRIEF_PERSONAL_COGNITIVE_GARDEN.md`
- `docs/SESSION_CONTINUITY_REPAIR_LAYER.md`
- `schemas/session-continuity-event.v0.1.json`
- `schemas/personal-cognitive-garden-update.v0.1.json`
- `docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md`
- `docs/ECOSYSTEM_INTEGRATION_MAP.md`

First ask:

```text
Fund a 3-6 month open-source evaluation harness for session-continuity failures in human-agent and multi-agent workflows.
```

### P0 — DevTools / coding-agent teams

Who:

```text
Codex-style tools
Claude/Cursor-style coding assistants
IDE agent teams
GitHub bot teams
CI autofix agents
agent orchestration platforms
```

Pain:

```text
The agent continued from the wrong context and produced a plausible but wrong next step.
```

Pitch:

```text
LS stops coding agents from continuing out of missing PR, branch, issue, or review context.
```

Offer:

```text
AI Co-work Continuity Audit for coding-agent workflows.
```

Audit scope:

- 20-50 coding-agent sessions;
- classify continuity breaks;
- identify missing context points;
- produce repair prompts;
- produce integration report;
- recommend gateway fields and artifact shape.

Show:

- `docs/CODEX_PLUGIN_DEMO.md`
- `plugins/ls-personal-cognitive-garden/README.md`
- `schemas/session-continuity-event.v0.1.json`
- `examples/session_continuity/missing_pr_context.json`

### P0 — Security / GRC / RegTech teams

Who:

```text
CISO
security engineering
GRC teams
audit teams
compliance engineering
AI risk teams
fintech/platform risk teams
```

Pain:

```text
The agent had access, but should this specific action have executed now?
```

Pitch:

```text
LS combines continuity checks with evidence gates so high-risk agent actions do not proceed from missing context.
```

Offer:

```text
Agent Action Continuity + Evidence Review
```

Audit scope:

- choose 5-10 high-risk agent actions;
- identify missing evidence;
- identify missing causal parent;
- classify reversibility;
- create stop reasons;
- produce reviewable audit packet.

### P1 — Enterprise AI adoption teams

Who:

```text
Head of AI transformation
VP Engineering
Head of Product Operations
internal AI platform teams
enterprise enablement teams
engineering excellence teams
```

Pain:

```text
We know people use AI more. We do not know if work is becoming safer, better, or more capability-building.
```

Pitch:

```text
LS measures whether AI sessions improve human capability and workflow continuity without exposing private growth data.
```

Offer:

```text
2-week AI Skill-Growth and Continuity Audit
```

Audit scope:

- 5-10 users;
- 50-100 AI sessions;
- private reviewed graph proposals for participants;
- aggregate-safe continuity/growth report;
- anti-surveillance boundary report.

### P1 — AI infrastructure investors

Who:

```text
AI infrastructure VC
DevTools VC
cybersecurity VC
enterprise AI VC
future-of-work VC
RegTech investors
AI safety philanthropists
```

Pain:

```text
Agents are becoming co-workers, but co-work breaks when context breaks.
```

Pitch:

```text
LS is the missing continuity layer between humans, agents, and meaning.
```

Investor wedge:

```text
Session continuity and repair for AI co-work.
```

Proof to show:

- public repo;
- schemas;
- examples;
- Codex plugin path;
- grant reviewer docs;
- ecosystem map;
- action/evidence stack relationship.

### P1 — Model labs / agent platform teams

Pain:

```text
How do we evaluate whether an agent preserved shared context across handoffs and tools?
```

Pitch:

```text
LS provides continuity events and repair artifacts for evaluating long-running agent sessions.
```

Offer:

```text
Session Continuity Evaluation Pack
```

Pack contents:

- missing PR context scenario;
- support/problem-solving mismatch scenario;
- stale branch/diff scenario;
- memory write without consent scenario;
- action without causal parent scenario;
- replayable trace fixtures.

### P2 — Coaching / learning / human development platforms

Pain:

```text
People use AI to learn and decide, but their growth does not compound into an owned development graph.
```

Pitch:

```text
LS turns AI sessions into human-owned skill capital with consent and review.
```

Offer:

```text
Private AI Growth Journal / Cohort Learning Pilot
```

## First paid offers

### Offer 1 — AI Co-work Continuity Audit

Best for:

```text
DevTools / coding-agent teams / AI-heavy engineering teams
```

Price range:

```text
$2,500 - $7,500 starter
$10,000 - $25,000 team/pilot
```

Deliverables:

- 20-100 session review;
- continuity rupture taxonomy;
- missing-context examples;
- repair prompt library;
- schema recommendations;
- short executive report;
- demo artifacts.

### Offer 2 — Agent Action Evidence Review

Best for:

```text
Security / GRC / RegTech / fintech / platform risk
```

Price range:

```text
$5,000 - $15,000 starter
$20,000 - $50,000 pilot
```

Deliverables:

- action boundary map;
- evidence gaps;
- causal parent gaps;
- reversibility classification;
- human approval requirements;
- stop reasons;
- audit packet.

### Offer 3 — AI Skill-Growth and Continuity Audit

Best for:

```text
enterprise AI adoption / engineering excellence / coaching / learning
```

Price range:

```text
$2,500 - $5,000 starter
$7,500 - $15,000 team audit
$20,000 - $50,000 advisory pilot
```

Deliverables:

- private participant summaries;
- aggregate-safe learning map;
- continuity/growth report;
- anti-surveillance boundary report;
- next-step implementation plan.

## First outreach messages

### DevTools / coding-agent angle

```text
Subject: Prevent coding agents from continuing from missing PR context

Hi <name>,

I am building LS, a local-first session continuity layer for AI co-work.

The narrow problem: coding agents often continue from missing PR, branch, diff, or review context and produce plausible but wrong next steps.

LS detects that as a continuity rupture, records the last shared point, and forces repair before continuation.

I have a small public artifact path: schema, examples, and a Codex plugin direction.

Would it be useful to run a small continuity audit on 20 real or synthetic coding-agent handoffs?
```

### Security / GRC angle

```text
Subject: Evidence before AI-agent action

Hi <name>,

I am working on LS / related open-source evidence-gate tooling for AI-agent workflows.

The premise is simple: valid credentials do not prove a valid action, and fluent agent output does not prove valid continuity.

Before an agent acts, we should know whether the context is intact, the intent is declared, the causal parent exists, and approval/reversibility constraints are satisfied.

Would it be useful to review one high-risk agent workflow and map the evidence gaps before automation?
```

### Grant / AI safety angle

```text
Subject: Open-source session continuity artifacts for agent oversight

Hi <name>,

I am developing LS, a local-first runtime for preserving continuity, consent, repair, and evidence across human-agent sessions.

The current research question: how can we detect hallucinated continuation before it becomes memory or action?

The repository now includes a session-continuity schema, examples, Personal Cognitive Garden governance artifacts, red-team anti-surveillance scenario, and a broader ecosystem map connecting causal memory, trace replay, and evidence gates.

I would value feedback on whether this fits your AI oversight / trustworthy AI funding priorities.
```

## What to show by audience

| Audience | Show first | Avoid |
|---|---|---|
| AI safety grants | `GRANT.md`, SCRL, PCG red-team, schema | investor hype |
| DevTools | Codex demo, missing PR context example | human-development philosophy first |
| Security/GRC | ProofPath/Pythia relation, action evidence gate | therapy/coaching language |
| Enterprise AI | AI Skill-Growth Audit, anti-surveillance boundary | employee scoring |
| Investors | wedge, market pain, artifact chain, first paid offers | too many repo names upfront |
| Model labs | evaluation pack, continuity events, trace/replay | replacing their models |
| Coaching/learning | PCG, consent, private growth graph | surveillance or psychological truth claims |

## Red lines

```text
Never sell LS as employee surveillance.
Never expose private cognitive gardens to managers.
Never claim final access to human intent.
Never let agent inference become identity truth without review.
Never present continuity repair as a hallucination cure-all.
Never blur research prototype with production compliance guarantees.
```

## First 30-day plan

### Week 1 — clean proof surface

- Merge and link SCRL docs.
- Merge and link ecosystem integration map.
- Add this target audience map to the reviewer path.
- Prepare a one-page continuity audit offer.

### Week 2 — create demo pack

- Create 3 continuity failure scenarios:
  - missing PR context;
  - support vs solution mismatch;
  - memory write without consent.
- Add expected LS decisions.
- Add one CLI/demo runner if feasible.

### Week 3 — outreach to 10 high-fit people

Prioritize:

```text
3 DevTools / coding-agent contacts
3 AI safety / governance reviewers
2 security/GRC contacts
2 enterprise AI adoption contacts
```

Do not mass-email.

Send artifact-first messages.

### Week 4 — convert to pilot or grant update

If interest appears:

```text
pilot: AI Co-work Continuity Audit
grant: session continuity evaluation harness
security: Agent Action Evidence Review
enterprise: AI Skill-Growth and Continuity Audit
```

## Bottom line

The first customers or funders are not people who want a chatbot.

They are people who already feel this expensive failure:

```text
AI work continued from broken context.
```

LS sells the repair:

```text
restore the shared point
prove the context
govern the memory
gate the action
```
