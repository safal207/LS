# Fellowship Evidence Audit

This document audits the current repository from the perspective of a
safety-oriented fellowship application.

The goal is to answer:

- what evidence already exists
- what is still weak
- what should be improved quickly

## Overall assessment

Current state:

- strong engineering prototype
- strong oversight framing
- good demo path
- incomplete benchmark and dataset story

In other words:

- the repository already supports a credible safety / oversight narrative
- the repository does not yet present a fully mature benchmark-grade evidence package

## What already counts as evidence

### 1. Oversight and operator controls

Evidence:

- `python/ls/agent_shell/cli.py`
- approval / inspect / artifact flows
- council-cycle execution path

Why it matters:

- demonstrates human-in-the-loop control
- shows that outputs are reviewable and not blindly trusted

Assessment:

- strong

### 2. Measurable council artifacts

Evidence:

- `python/ls/cognition/council_contribution_ledger.py`
- `artifacts/council-ledger/*.json`
- council scorecard export pipeline

Why it matters:

- shows model participation, adoption, contribution, and receiver resonance

Assessment:

- medium

Reason:

- the schema and pipeline are strong
- the artifact volume is still too small
- some artifacts are demo or low-signal

### 3. Replay and traceability

Evidence:

- LTP export / inspect flows
- replay-oriented CLI paths
- public and local scorecards

Why it matters:

- supports post-hoc debugging and governance

Assessment:

- medium to strong

Reason:

- the mechanism exists
- the repo still needs a cleaner trace dataset package

### 4. Quality and evaluation infrastructure

Evidence:

- CI quality gates
- quality-report pipeline
- LiminalQA integration
- machine-readable reports

Why it matters:

- demonstrates evaluability and structured test intelligence

Assessment:

- strong

### 5. Benchmark evidence

Evidence:

- `ghostgpt-ls-landing/src/data/operatorDeltaBenchmark.json`

Why it matters:

- proves at least one measurable operator benefit

Assessment:

- weak to medium

Reason:

- it is explicitly a local benchmark snapshot on one machine
- good for demo
- not yet strong as a fellowship-grade benchmark artifact

## Current gaps

### Gap 1. Too few real council cycles

Problem:

- scorecard is built from very few real cycles
- some council-ledger files are demo or dry-run style artifacts

Why it matters:

- reviewers may see the instrumentation, but not enough evidence that it was exercised meaningfully

### Gap 2. No clean replayable dataset package yet

Problem:

- traces and ledger artifacts exist
- but there is no compact, curated dataset folder or manifest

Why it matters:

- a fellowship reviewer will trust a structured dataset package more than scattered artifacts

### Gap 3. No benchmark note with setup and limitations

Problem:

- the benchmark snapshot exists
- but there is no concise note describing:
  - setup
  - baseline
  - metrics
  - limitations

Why it matters:

- this makes the benchmark look more like marketing than evaluation

### Gap 4. No short technical note on attribution

Problem:

- contribution attribution is implemented
- but not yet written up as a focused technical artifact

Why it matters:

- this is one of the most novel parts of the repository
- it should be documented as a method, not only as code

## Evidence verdict by category

| Category | Current state | Verdict |
|---|---|---|
| Oversight workflow | Implemented and demoable | Strong |
| Approval-safe operator path | Implemented and visible | Strong |
| Council contribution instrumentation | Implemented, lightly exercised | Medium |
| Replay / traceability | Implemented, not yet packaged as dataset | Medium |
| Benchmark evidence | Snapshot exists, weak methodology packaging | Weak to Medium |
| Research-ready artifact bundle | Planned, not yet complete | Weak |

## What is already good enough for the application

These parts are already credible:

- the repository is clearly not just another chatbot wrapper
- the operator / oversight framing is real
- human approval, replay, and quality instrumentation are already implemented
- the project demonstrates strong engineering effort in safety-adjacent infrastructure

## What would materially strengthen the application

These additions would have high leverage:

1. 10 to 30 real council cycles
2. one curated replayable trace dataset folder
3. one benchmark note with setup and limitations
4. one attribution note with method and caveats

## Recommendation

Apply with the current repository if needed.

But if there is time for one more push before final submission, focus on:

- a small benchmark package
- a small dataset package
- one technical note

That is the shortest path from "strong prototype" to "credible research artifact".
