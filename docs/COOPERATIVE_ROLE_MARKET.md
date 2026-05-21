# Cooperative Role Market

LS can treat AI co-work as a market of verified roles, not only as a set of
model calls.

The core observation:

```text
if there is a customer and a consumer,
the system can discover a designer, executor, and verifier
```

In LS terms:

```text
need
-> role design
-> execution
-> verification
-> adoption
-> route memory
```

## Why This Matters

Most agent systems ask:

```text
which model should answer?
```

LS should ask:

```text
which role is missing in this process?
who is best at that role?
was the contribution verified by evidence and adoption?
```

This turns cooperative precision into a role market:

```text
customer creates demand
consumer confirms value
designer builds the route
executor performs the work
verifier checks evidence and risk
LS records contribution and precision
```

## Core Roles

| Role | Question | Value signal |
|---|---|---|
| Customer | What needs to be done? | Clear demand and constraints |
| Consumer | Who receives value? | Adoption, feedback, usefulness |
| Designer | What route should solve it? | Better route, lower uncertainty |
| Executor | Who does the work? | Completed artifact |
| Verifier | Is it true, safe, and useful? | Evidence, risk reduction |
| Operator | Who authorizes continuation? | Consent and final decision |

These roles can be filled by humans, models, tools, or deterministic LS checks.

## PR Review Example

```text
customer: maintainer wants a pull request reviewed
consumer: repository users need safer merged code
designer: chooses draft -> critic -> verifier -> final route
executor: drafts the review
verifier: checks diff evidence, tests, and risky changes
operator: maintainer decides whether to merge or revise
LS: stores route reward and contribution scores
```

The question becomes:

```text
not "which model is best?"
but "which role arrangement produced verified value?"
```

## How It Connects To Current LS

Current pieces:

- `scripts/run_pr_review_trail_artifact.py` builds a real diff artifact.
- `scripts/run_free_pr_review_route.py` creates role prompts without paid APIs.
- `python/modules/graph/trail_updater.py` computes route reward.
- `python/ls/cognition/council_contribution_ledger.py` already computes best contributor scores.
- `docs/COOPERATIVE_PRECISION_ROADMAP.md` defines the precision roadmap.

Missing bridge:

```text
PR review artifact
-> role outputs
-> contribution scores by role
-> role reputation
-> better role matching next time
```

## Metrics

### Route Metrics

Route metrics answer:

```text
which process worked?
```

Examples:

- route reward;
- average quality;
- hallucination risk;
- latency;
- route reuse rate.

### Role Metrics

Role metrics answer:

```text
who contributed useful value inside the route?
```

Examples:

- accepted findings;
- evidence quality;
- risk reduction;
- false positives;
- unsupported claims;
- consumer adoption.

### Synergy Metric

Synergy answers:

```text
did cooperation beat the best single participant?
```

Simple form:

```text
synergy = cooperative_result - best_single_result
```

In the current demo:

```text
0.91 - 0.68 = 0.23
```

That is a measured cooperative lift, not a claim that the system is generally
smarter.

## Role Matching Loop

```text
1. Customer creates a task.
2. Consumer or maintainer defines acceptance criteria.
3. LS selects or proposes a route.
4. Roles produce outputs.
5. Verifier checks evidence.
6. Operator accepts, rejects, or asks for repair.
7. LS updates route reward and role contribution.
8. Future tasks start with better role matching.
```

## Free-Only Start

The role market can start without paid APIs:

```bash
python scripts/run_free_pr_review_route.py
```

This produces role prompts for:

- current Codex session;
- local model;
- deterministic LS checks;
- human review.

The market does not need paid execution to begin measuring:

```text
role -> artifact -> evidence -> contribution score
```

## Executable Demo

Run the first role-market measurement demo:

```bash
python scripts/run_role_market_demo.py
```

Expected shape:

```text
Need: Safer pull-request review before merge.
Best route: pr_review>designer>executor>verifier>final
Baseline quality: 0.68
Cooperative quality: 0.92
Synergy quality lift: +0.24
Best role contribution: route_designer
Decision: use cooperative role route next time
```

This is still synthetic, but it proves that LS can express:

```text
need -> role route -> contribution score -> best role -> next route choice
```

The best contribution can be route design, not just execution: LS can credit the
role that chose the better cooperative process.

## Real PR Role Market Demo

Run role scoring over the latest real PR-style git diff:

```bash
python scripts/run_pr_role_market_demo.py
```

Example shape:

```text
Diff source: HEAD~1..HEAD
Signals: missing_tests, large_diff
Live model calls: false
Baseline reward: 0.5167
Cooperative reward: 0.6639
Best role contribution: risk_critic
Best actor/model: gonka / qwen/qwen3-235b-a22b-instruct-2507-fp8
```

This connects the role market to the existing PR-review trail artifact. The
numbers are diff-dependent: LS is scoring the route and roles for this concrete
review, not assigning a permanent global rank to people or models.

The demo only names actors already present in LS:

```text
codex-self-use
local-qwen / qwen2.5:7b
local-qwen-light / qwen2.5:1.5b
gonka / qwen/qwen3-235b-a22b-instruct-2507-fp8
mimo / mimo-v2-flash
human_operator
```

`live_model_calls: false` means the current script scores a real PR-review
artifact deterministically. The actor roster is explicit so future live role
outputs can be attached without pretending that unsupported models were used.

Attach real role outputs from those actors:

```bash
python scripts/run_pr_role_market_demo.py \
  --role-outputs docs/examples/pr_role_outputs.sample.json
```

Or generate a template for the current diff:

```bash
python scripts/run_pr_role_market_demo.py \
  --write-role-output-template reports/role_market/role_outputs.template.json
```

The role-output file is the bridge from a real Codex/local-model/human run back
into LS scoring. Unknown actors are rejected so the report cannot silently claim
that unsupported models participated.

Run a small batch benchmark over recent history:

```bash
python scripts/run_pr_role_market_batch.py \
  --last 10 \
  --role-outputs docs/examples/pr_role_outputs.sample.json \
  --markdown-output reports/role_market/pr_role_market_history.md
```

This turns the single-diff proof into a table of repeated measurements:

```text
commit -> signals -> baseline reward -> cooperative reward -> lift -> best role -> best actor
```

## Roadmap

### Phase 1: Role Schema

Add role fields to review artifacts:

```json
{
  "role": "risk_critic",
  "actor": "codex-session",
  "output": "...",
  "evidence": ["diff hunk", "test output"],
  "accepted": true
}
```

### Phase 2: Contribution Scoring

Connect role outputs to contribution scoring:

```text
accepted evidence-backed finding -> reward
unsupported claim -> penalty
false positive -> penalty
useful route design -> designer reward
consumer adoption -> confidence boost
```

### Phase 3: Role Reputation

Track where each actor is useful:

```text
best risk critic
best evidence verifier
best route designer
best final summarizer
```

This should be role-specific, not a general model ranking.

### Phase 4: Open Task Market

Let contributors pick clear roles:

```text
write fixture
improve risk detector
design better route
verify artifact
create benchmark report
```

## Guardrails

Do not turn this into hidden labor scoring or surveillance.

Rules:

- score artifacts, not people as whole identities;
- keep role reputation contextual;
- require evidence for contribution claims;
- keep human approval for durable state;
- let contributors inspect and contest scoring.

## Short Positioning

> LS turns AI co-work from a pile of answers into a market of verified roles and
> contributions.

> The network becomes more precise when the right role finds the right task and
> the contribution is verified.
