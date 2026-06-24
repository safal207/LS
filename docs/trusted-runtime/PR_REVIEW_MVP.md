# Trusted PR Review MVP

Status: deterministic local product slice for issue #598.

## What it demonstrates

A temporary PR review becomes a continuous, inspectable, replayable, and reusable LS artifact.

```text
git diff
-> reviewer / risk critic / verifier
-> deterministic route decisions
-> Cognitive Trail
-> CML causal audit
-> evidence decision
-> ProofPath authorization
-> CaPU commit-before-effect
-> LTP replay
-> reusable PR-review artifact
```

## Five-minute walkthrough

### 1. Run all scenarios

```bash
PYTHONPATH=.:python:python/modules \
  python scripts/run_trusted_pr_review.py --scenario all
```

Outputs are written under:

```text
build/trusted-pr-review/
├── index.json
├── allow/
├── hold/
└── block/
```

### 2. Read the human summary

Open:

```text
build/trusted-pr-review/allow/review.md
build/trusted-pr-review/hold/review.md
build/trusted-pr-review/block/review.md
```

Each summary shows the evidence decision, causal status, replay status, routes, role contributions, findings, and whether the protected effect was written.

### 3. Inspect the ALLOW artifact

The successful scenario produces:

```text
allow/
├── artifact.json
├── review.md
├── workflow-plan.json
├── causal-audit.json
├── evidence-decision.json
├── execution-journal.json
├── events.jsonl
├── protected/
│   └── <execution-id>.review.json
├── proofpath/
│   ├── manifest.json
│   ├── decisions.jsonl
│   ├── hash-chain.json
│   ├── verifier-result.json
│   ├── privacy-report.json
│   └── README.md
└── replay/
    ├── trace.jsonl
    ├── replay-record.json
    ├── conformance-report.json
    ├── resume-checkpoint.json
    └── README.md
```

`artifact.json` connects route, evidence, contribution, decision, execution, and replay references in one integrity-bound payload.

### 4. Verify the negative scenarios

The HOLD fixture changes account limits without changed test evidence. It stops before authorization.

The BLOCK fixture adds dynamic execution of client-controlled input. It stops before authorization.

Neither scenario creates:

```text
protected/*.review.json
artifact.json
proofpath/
```

They still produce a durable trail, evidence decision, replay report, and readable review summary.

### 5. Run the acceptance tests

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest \
    python/tests/test_trusted_pr_review_scenarios.py \
    python/tests/test_trusted_pr_review_failures.py
```

## Before and after

### Before LS continuity

```text
diff
-> temporary model response
-> reviewer manually decides what happened
-> context and responsibility disappear
```

### After this MVP

```text
diff
-> declared roles
-> explainable routes
-> linked contributions
-> causal validation
-> evidence gate
-> signed authorization evidence
-> committed protected effect
-> deterministic replay
-> reusable artifact
```

## Scenario contract

| Scenario | Evidence decision | Authorization | Protected write | Replay |
|---|---|---:|---:|---|
| ALLOW | sufficient evidence, no blocking risk | yes | yes | ADMISSIBLE |
| HOLD | missing changed-test evidence | no | no | DRIFTED partial path |
| BLOCK | executable-risk signature | no | no | ADMISSIBLE blocked path |

A blocked terminal path can be replay-admissible: `ADMISSIBLE` means the stored path faithfully followed policy, not that the proposed code was approved.

## Protected effect versus evidence export

The CaPU-protected effect is the single review-result file under `protected/`. It is written only after durable commit.

Workflow plans, decisions, reports, and replay files are evidence exports. They describe the decision process and are not the approved protected business effect.

## Failure fixtures

The test suite includes:

- a high-impact action with a missing causal parent;
- an authorization that expires before CaPU execution;
- HOLD and BLOCK paths that must never write the protected result;
- artifact schema and digest validation.

## Non-claims

This MVP does not claim:

- that a live LLM reviewed the code;
- complete static-analysis or secret-scanning coverage;
- production-grade distributed event storage;
- regulatory certification;
- that replay repeats external effects;
- that an `ALLOW` decision proves the code is bug-free.

The analysis and role outputs are deterministic local reference implementations. Real model, CML, Pythia, ProofPath, CaPU, LTP, and LiminalDB integrations remain replaceable adapters behind the same responsibility boundaries.

## Production next steps

A hosted or enterprise version still needs authenticated repository access, tenant isolation, concurrent-writer fencing, encrypted storage, retention and erasure controls, policy administration, real test-result ingestion, human approval UX, and signed release evidence.
