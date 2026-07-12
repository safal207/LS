# OpenAI Build Week 2026 — LS Submission Plan

Status: **provisional until the official rules and tracks are published on July 13, 2026**

Submission window: **July 13–21, 2026**

Working project name: **LS — Trust Layer for AI Software Delivery**

Repository: `safal207/LS`

Baseline before Build Week work: `caaa5ed758c965127834690dfd248e0496780e74`

Build Week branch: `build-week-2026`

---

## 1. Problem

AI coding agents can create, review, and approve software changes, but CI/CD workflows often trust mutable labels, reviewer logins, stale approvals, or incomplete execution evidence.

This creates a dangerous gap:

```text
AI produces a decision
        ↓
workflow observes an approval-like signal
        ↓
signal is treated as authority
        ↓
the decision affects delivery without proving
who made it, which code state it belongs to,
or whether required checks actually ran
```

The Build Week wedge is deliberately narrow:

> **Before an AI-generated decision affects software delivery, prove that the decision belongs to the current code state and came through an allowed, evidence-bearing route.**

---

## 2. Solution

LS acts as a fail-closed Change Intelligence Gate around AI-generated pull requests.

It verifies evidence such as:

- exact PR head SHA;
- reviewer identity and account type;
- review state and freshness;
- required deterministic checks;
- distinction between `PASS`, `FAIL`, and `NOT_RUN`;
- independent review evidence;
- human adjudication when evidence is incomplete or conflicting.

Output:

```text
AI work → evidence → trust verification → explainable verdict → action or block
```

LS does not claim that an AI reviewer is always correct. It proves whether a specific decision is admissible for the current repository state.

---

## 3. Winning attack scenario

### Primary scenario: stale approval against a changed PR head

```text
PR head at approval time: SHA-A
        ↓
AI reviewer approves SHA-A
        ↓
new commit changes PR head to SHA-B
        ↓
old approval still exists
        ↓
naive workflow sees APPROVED
        ↓
LS compares review SHA with current PR head
        ↓
SHA mismatch
        ↓
UNTRUSTED — BLOCKED
```

### Secondary adversarial scenarios

1. A login resembles a trusted bot, but the account type or actor evidence is invalid.
2. A required review lane did not run but is mistakenly interpreted as passing.
3. A foreign or unrelated workflow event attempts to influence a trusted run.
4. Evidence exists, but it belongs to another commit or incomplete record set.
5. A valid current-head review with complete evidence is allowed.

The final demo should show one primary scenario in depth and summarize the secondary matrix.

---

## 4. Winning demo

Target length: **90–120 seconds**, subject to official rules.

### 0–15 seconds — The risk

Show a pull request whose current head is `SHA-B` while an AI approval belongs to `SHA-A`.

Narration:

> AI agents can review and approve code, but an approval is not enough. We need to prove that it belongs to the exact code being shipped.

### 15–35 seconds — Naive acceptance

Show the approval-like signal that a simple workflow could accept.

```text
reviewer: trusted-looking bot
state: APPROVED
review commit: SHA-A
current PR head: SHA-B
```

### 35–60 seconds — LS verification

Show LS checking:

```text
actor             → observed
account type       → verified or rejected
review state       → APPROVED
review commit SHA  → SHA-A
current PR SHA     → SHA-B
required lanes     → PASS / FAIL / NOT_RUN
```

Verdict:

```text
UNTRUSTED — BLOCKED
Reason: approval does not belong to the current PR head
```

### 60–85 seconds — Trusted path

Run the same gate with:

- allowed reviewer;
- current PR head SHA;
- required checks executed;
- complete evidence.

Verdict:

```text
TRUSTED — ELIGIBLE FOR HUMAN-AUTHORIZED DELIVERY
```

### 85–110 seconds — Evidence and impact

Show:

- machine-readable trust report;
- human-readable explanation;
- adversarial test matrix;
- reproducible command.

Final line:

> Codex helps teams build software faster. LS helps teams prove which AI decisions can be trusted before they affect delivery.

---

## 5. Codex role

Codex must be structurally important, not a decorative mention.

Planned roles:

1. **Builder:** implement or improve the Build Week demo path and evidence surface.
2. **Reviewer:** inspect the change and produce review evidence tied to the exact PR head.
3. **Adversarial collaborator:** generate or execute negative scenarios against the trust gate.
4. **Trace participant:** leave an auditable record of what it changed, checked, and concluded.

Submission explanation:

> Codex participates in the software-delivery loop, while LS verifies the provenance, freshness, completeness, and admissibility of the evidence produced around that work.

Required proof:

- list of Codex-assisted Build Week commits or PRs;
- exact tasks delegated to Codex;
- examples where LS accepted or rejected Codex-related evidence;
- human decisions preserved explicitly.

---

## 6. Required evidence

All claims must be backed by reproducible artifacts.

Planned structure:

```text
build-week/
  README.md
  demo/
    stale-approval.json
    spoofed-reviewer.json
    required-check-not-run.json
    trusted-current-head.json
  evidence/
    attack-matrix.md
    test-results.json
    trust-report.example.json
    codex-contribution-log.md
  scripts/
    run_demo.sh
```

Minimum evidence set:

- one-command demo or shortest practical equivalent;
- deterministic positive and negative fixtures;
- expected verdict for every fixture;
- actual test output;
- exact commit SHA used for the recorded demo;
- explanation of `PASS`, `FAIL`, and `NOT_RUN`;
- no invented benchmark numbers.

---

## 7. Product positioning

### One sentence

> LS is an evidence-backed trust layer that verifies whether an AI decision belongs to the current code state before that decision can influence software delivery.

### 15-second version

> AI coding agents can write and approve code, but approvals can be stale, spoofed, or incomplete. LS freezes the exact PR head, verifies the evidence, and blocks untrusted AI decisions before they affect CI/CD.

### Judge-friendly metaphor

> **Airport security for AI-generated code:** identity, route, current destination, and evidence are checked before the decision is allowed through.

### What LS is not

- not another generic chatbot;
- not a claim that multiple models automatically create truth;
- not a replacement for human authorization;
- not a broad rewrite of every LS direction during one hackathon.

---

## 8. Out of scope

To protect the deadline and story clarity, this submission will not attempt to:

- demonstrate every LS subsystem;
- redesign the entire repository architecture;
- build a full commercial dashboard;
- support every CI provider;
- claim perfect AI-review accuracy;
- eliminate human review;
- complete unrelated personal-memory or cognitive-garden features;
- add integrations that do not strengthen the primary demo.

Scope rule:

> If a task does not improve the attack → detect → block story, reproducibility, Codex relevance, or submission clarity, it is deferred.

---

## 9. Submission assets

Required or expected, pending official rules:

- Devpost registration;
- project title and tagline;
- English project description;
- public repository link;
- working demo or reproducible local run;
- short demo video;
- architecture diagram;
- screenshots or GIF;
- explanation of Codex and GPT-5.6 usage;
- team/member details;
- category or track selection;
- disclosure of pre-existing work versus Build Week work;
- license and dependency review;
- final rules and country-eligibility confirmation.

---

## 10. Pre-existing work disclosure

LS existed before OpenAI Build Week.

The submission must clearly separate:

### Before Build Week

- existing LS architecture and repository;
- current Change Intelligence Gate concepts;
- existing evidence, continuity, conformance, and review work;
- baseline commit: `caaa5ed758c965127834690dfd248e0496780e74`.

### Built during Build Week

To be filled with exact commits and outcomes after work begins:

| Commit / PR | Build Week contribution | Codex role | Evidence |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

No pre-existing functionality should be presented as newly built during the event.

---

## 11. Self-scorecard

Target before submission: **85/100 or higher**.

| Criterion | Weight | Passing condition |
| --- | ---: | --- |
| Problem clarity | 15 | Understandable without GitHub Actions expertise |
| Demo impact | 20 | Attack and block are visible in under 60 seconds |
| Technical execution | 20 | Real current-head and evidence checks work end to end |
| Codex relevance | 15 | Codex is part of the actual workflow and contribution trail |
| Potential impact | 10 | Reusable beyond this repository |
| UX and explanation | 10 | Verdict explains what failed and why |
| Reproducibility | 10 | Judge can run or inspect evidence without guesswork |

---

## 12. Timeline

### Before July 13

- register on Devpost;
- preserve this baseline and branch;
- prepare the primary scenario;
- do not make claims about unpublished rules.

### July 13

- review official rules, tracks, prizes, judging criteria, and eligibility;
- update this plan immediately;
- choose the final track;
- freeze the final scope.

### July 14–16

- implement the primary end-to-end scenario;
- add positive and negative fixtures;
- produce the first machine-readable trust report.

### July 17–18

- adversarial testing;
- remove flaky behavior;
- improve human-readable verdicts;
- document the architecture and Codex contribution trail.

### July 19

- record a rough demo;
- test whether a person unfamiliar with LS can explain the project correctly.

### July 20

- final video;
- complete Devpost draft;
- test all links and reproduction steps in a clean environment.

### July 21

- critical fixes only;
- submit with a safety margin before the deadline.

---

## 13. Immediate next actions

1. Join the OpenAI Build Week hackathon on Devpost.
2. Review the official rules as soon as they are published.
3. Create the first Build Week implementation issue from this plan.
4. Build the stale-approval fixture and trusted-current-head control fixture.
5. Produce a minimal trust report that clearly explains the verdict.
6. Record all Build Week commits and Codex contributions in this document.

---

## 14. Decision rule

The submission succeeds when a judge can answer all four questions quickly:

1. What can go wrong?
2. What does LS verify?
3. What does the demo prove?
4. Why is Codex essential to the project?

If any answer is unclear, simplify the story before adding more features.
