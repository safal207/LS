# Grant Reviewer Packet 2026

This packet is a compact reviewer path for the LS / Liminal Stack ecosystem and its connected implementation repositories.

It is written for grant reviewers, technical evaluators, fellowship reviewers, and safety-infrastructure funders who need to understand what exists today, what can be inspected, what is not claimed, and what funding would unlock next.

## One-sentence summary

This is not a bundle of unrelated repositories. It is a connected evidence stack for inspecting human-plus-agent coordination, measurable cooperative routes, causal validity, trace continuity, evidence gates, and action boundaries.

```text
LS / Liminal Stack
  -> governance, coordination, continuity, Cognitive Trail contracts, and reviewer surface
Cognitive Trail Contract
  -> schema, generated PR-review sample, benchmark note, validator, generator, CI, and reviewer quickstart
ProofPath / Compute Witness
  -> executable action-boundary and reviewable compute-evidence hub
PythiaLabs
  -> deterministic evidence-gate project surface
CML
  -> causal-validity and why-allowed layer
LTP / L-THREAD
  -> trace, replay, continuity, and admissibility-inspection layer
```

## Core research hypothesis

High-risk AI-agent actions should not be trusted only because a model produced them, a tool call succeeded, or credentials were valid.

They should carry inspectable evidence of:

```text
intent
-> scope
-> cooperative route evidence
-> causal authorization
-> trace continuity
-> evidence-gate decision
-> action-boundary decision
-> auditability
```

The current ecosystem tests whether this can be expressed as public repositories, committed fixtures, executable validators, CI checks, reviewer paths, and explicit non-claims.

## What exists today

| Layer | Repository / surface | Evidence available today |
| --- | --- | --- |
| Governance and continuity surface | [LS](https://github.com/safal207/LS) | Council cycles, approval-safe workflows, personal-agent gateway framing, benchmark docs, safety positioning, Cognitive Trail contracts, and this reviewer packet. |
| Measurable cooperative route artifact | [Cognitive Trail Reviewer Quickstart](COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md) | Contract schema, checked-in generated PR-review sample, PR-review benchmark note, validator, generator, CI workflow, runtime report folder, and explicit interpretation boundary. |
| Ecosystem map | [ProofPath ecosystem graph](https://github.com/safal207/ProofPath/blob/main/docs/ECOSYSTEM_GRAPH.md) | Cross-repository graph connecting LS, ProofPath, Compute Witness, PythiaLabs, CML, LTP, T-Trace, and CaPU. |
| Executable action boundary | [ProofPath](https://github.com/safal207/ProofPath) | Rust verifier, gateway, action-context profile, dangerous-action demos, real-model demo, audit logs, reviewer docs. |
| Reviewable compute evidence | [Compute Witness path](https://github.com/safal207/ProofPath/blob/main/docs/COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md) | Manifests, receipts, audit fixtures, broken-evidence challenges, Python conformance, Rust CLI, Rust audit-hash verification, CI checks. |
| Evidence-gate surface | [PythiaLabs](https://github.com/safal207/pythiaLabs) | Deterministic evidence-gate framing and continuation link to ProofPath / Compute Witness. |
| Causal validity | [Causal Memory Layer](https://github.com/safal207/Causal-Memory-Layer) | Causal chain validation, authorization-lineage checks, benchmark evidence, hosted audit API MVP docs. |
| Trace and replay | [LTP / L-THREAD](https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-) | Deterministic replay, two-phase inspection, admissibility decisions, conformance paths, commercial/audit docs. |

## What to inspect first

A reviewer can inspect the ecosystem without reading every file.

### 1. Start with LS

Read:

- [LS README](../README.md)
- [Ecosystem Reviewer Index](ECOSYSTEM_REVIEWER_INDEX.md)
- [Safety Programs Positioning](SAFETY_PROGRAMS_POSITIONING.md)
- [Cognitive Trail Reviewer Quickstart](COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md)

Purpose:

```text
Understand the broad governance and reviewer surface, then verify one LS-local measurable route contract.
```

### 2. Inspect the Cognitive Trail contract

Read:

- [Cognitive Trail Run Contract](COGNITIVE_TRAIL_RUN_CONTRACT.md)
- [Cognitive Trail PR-Review Benchmark Note](COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md)
- [Cognitive Trail Network](COGNITIVE_TRAIL_NETWORK.md)
- [Generated PR-review trail sample](../examples/trails/generated_pr_review_sample.json)
- [Cognitive Trail Contract CI workflow](../.github/workflows/cognitive_trail_contract.yml)

Purpose:

```text
Verify that LS can record, validate, and repeat-measure which cooperative route made a concrete PR-review task more precise.
```

### 3. Inspect the executable hub

Read:

- [ProofPath README](https://github.com/safal207/ProofPath)
- [ProofPath Ecosystem Graph](https://github.com/safal207/ProofPath/blob/main/docs/ECOSYSTEM_GRAPH.md)
- [Compute Witness Grant Reviewer Path](https://github.com/safal207/ProofPath/blob/main/docs/COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md)

Purpose:

```text
Verify that the abstract safety claim has executable artifacts and CI-backed evidence.
```

### 4. Inspect causal validity and replay layers

Read:

- [CML README](https://github.com/safal207/Causal-Memory-Layer)
- [LTP README](https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-)

Purpose:

```text
Understand how causal authorization and trace continuity support the same research direction.
```

## Commands and inspection paths

The exact commands vary by repository. The current LS-local route review path is centered on the Cognitive Trail contract, while the current executable action-boundary path is centered on ProofPath / Compute Witness.

### Cognitive Trail contract validation

From the LS repository root:

```bash
python3 -m pip install jsonschema
python3 scripts/validate_cognitive_trail_runs.py
```

Expected intent:

```text
validate checked-in Cognitive Trail examples against schema and semantic invariants
```

### Cognitive Trail generated artifact path

From the LS repository root:

```bash
python3 scripts/generate_pr_review_trail_run.py --last 10 --validate
```

Expected intent:

```text
generate a runtime PR-review trail-run artifact, validate it, and keep it under reports/trails/*.json without committing local runtime reports
```

The canonical committed example is:

```text
examples/trails/generated_pr_review_sample.json
```

The short benchmark interpretation is:

```text
docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md
```

### Compute Witness conformance

From the ProofPath repository root:

```bash
python3 scripts/validate_compute_witness.py
```

Expected intent:

```text
validate manifests, receipts, audit hashes, causal parent continuity, and challenge fixtures
```

### Compute Witness Rust CLI path

From the ProofPath repository root:

```bash
cargo run -q -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json
```

Fixture regression check:

```bash
cargo run -q -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json > /tmp/rust_receipt_draft.accept.json
diff -u examples/compute-witness/rust_receipt_draft.accept.json /tmp/rust_receipt_draft.accept.json
```

Expected intent:

```text
show that the Rust verifier path produces stable receipt-draft evidence and that CI detects drift
```

### CML local validation

From the CML repository root:

```bash
pip install -e ".[dev]"
pytest
```

Reviewer intent:

```text
validate causal-memory and authorization-lineage semantics
```

### LTP local validation

From the LTP repository root:

```bash
corepack enable
corepack prepare pnpm@9.15.0 --activate
pnpm install --frozen-lockfile
pnpm test
pnpm test:conformance
```

Reviewer intent:

```text
validate trace/replay and conformance surfaces
```

## Why this differs from a productivity dashboard

The ecosystem is not primarily a dashboard for improving AI output quality.

It is infrastructure for reviewable AI-agent behavior:

```text
ordinary dashboard
  -> shows outputs, metrics, and workflow status

this ecosystem
  -> asks whether memory, action, compute, route reuse, or continuation should be allowed at all
  -> records why it was allowed, blocked, rejected, held, or marked for repeat
  -> makes the evidence inspectable and regression-testable
```

The key distinction is not UI polish. It is the shift from:

```text
what did the model say?
```

to:

```text
what evidence allows this output, memory write, route, compute result, or action to become durable, repeatable, or executable?
```

## Evidence chain

The strongest current evidence chain now has two connected parts.

### LS-local measurable route chain

```text
LS reviewer and governance surface
  -> Cognitive Trail Run contract
  -> JSON Schema
  -> checked-in generated PR-review sample
  -> PR-review benchmark note
  -> validator with semantic checks
  -> PR-review trail generator
  -> generate-and-validate command
  -> Cognitive Trail Contract CI workflow
  -> runtime reports folder with gitignored generated JSON
```

This chain shows how LS turns a cooperative PR-review route into a validated artifact with a repeatability decision.

### ProofPath / Compute Witness executable evidence chain

```text
ProofPath ecosystem graph
  -> Compute Witness job manifest
  -> compute receipt
  -> audit log entry
  -> canonical SHA-256 audit verification
  -> optional causal parent receipt check
  -> broken-evidence challenge fixtures
  -> Rust verifier adapter and CLI
  -> expected Rust output fixture
  -> CI regression checks
```

This chain shows how executable action-boundary and compute-evidence claims are turned into commands, fixtures, receipts, and CI checks.

Together, these evidence chains are narrow, but concrete. They give reviewers artifacts, commands, and expected behavior rather than only a conceptual claim.

## Current limitations and non-claims

This packet does not claim that the ecosystem is complete or production-certified.

It does not currently prove:

- universal model alignment;
- model truthfulness;
- certified regulatory compliance;
- production key management;
- GPU hardware identity;
- trusted execution environment state;
- zkML execution correctness;
- distributed settlement;
- global ranking of models, roles, tools, or human contributors;
- that LS already operates a global live Cognitive Trail Network;
- full cross-repository replay or dispute resolution;
- full end-to-end production deployment across all layers.

The current claim is narrower and testable:

```text
The ecosystem already contains connected, public, inspectable artifacts for reviewing human-plus-agent coordination, measurable cooperative routes, causal validity, trace continuity, evidence gates, action boundaries, and compute-evidence checks.
```

## What funding unlocks next

Funding would harden and connect existing artifacts rather than start from zero.

### Workstream 1: Cognitive Trail hardening

```text
Cognitive Trail contract
+ generated trail samples
+ PR-review benchmark note
+ validator
+ generator
+ CI workflow
+ reviewer quickstart
```

Deliverables:

- richer PR-review trail-run benchmark set;
- generated reports promoted into curated examples when stable;
- stronger schema versioning and migration notes;
- role-output attachment fixtures;
- clearer route-repeatability evaluation across more diffs.

### Workstream 2: Cross-repo conformance

```text
LS reviewer packet
+ Cognitive Trail route artifacts
+ ProofPath evidence hub
+ CML causal validation
+ LTP trace/replay
+ PythiaLabs evidence gates
```

Deliverables:

- shared terminology and reviewer routes;
- compatibility notes between Cognitive Trails, CML, LTP, ProofPath, and Compute Witness;
- small cross-repo demo scenario;
- CI-backed conformance snapshots where feasible.

### Workstream 3: Deeper Rust verification

Deliverables:

- more Compute Witness verification in Rust;
- richer challenge fixture support;
- audit-packet verification beyond the first audit-hash primitive;
- stable CLI outputs for reviewer and pilot usage.

### Workstream 4: Pilot integrations

Deliverables:

- one or two narrow pilot workflows;
- manifest and receipt emission for real agent actions;
- reviewable audit packets;
- short risk notes explaining what passed, failed, and remains unproven.

### Workstream 5: Research and reviewer artifacts

Deliverables:

- technical note or preprint;
- benchmark note;
- demo video or reproducible walkthrough;
- structured reviewer packet updates;
- external contributor tasks.

## Minimal funding case

The fundable claim is:

```text
This project has moved from philosophy to artifacts.
```

Current state:

```text
conceptual frame
-> public repositories
-> reviewer paths
-> committed fixtures
-> executable validators
-> generators
-> Rust implementation path
-> CI checks
-> explicit limitations
```

Funding would support hardening, integration, and evidence quality.

## Recommended reviewer decision

A reviewer should not evaluate this as a mature production compliance platform.

A fair evaluation frame is:

```text
early-stage open-source safety infrastructure with unusually concrete artifacts for a solo/independent research effort
```

The strongest reason to fund is not that every layer is finished. The strongest reason is that the core research direction has already been materialized into inspectable, executable, and extensible evidence surfaces.

## One-page mental model

```text
LS
  asks whether agent output can become memory, profile state, coordination artifact, route artifact, or action under human-owned governance.

Cognitive Trail Contract
  asks whether one cooperative route made one concrete task more precise, with evidence strong enough to decide whether that route should be repeated.

CML
  asks why an action was allowed and whether authorization lineage is causally valid.

LTP
  asks whether the execution path can be replayed and inspected.

PythiaLabs
  asks whether a high-risk agentic action should pass through an evidence gate.

ProofPath
  asks whether an authenticated request should become an executed high-risk action.

Compute Witness
  asks whether an AI/agent compute result can be trusted as reviewable evidence.
```

Together:

```text
human-owned governance
  -> measurable cooperative route
  -> causal authorization
  -> trace continuity
  -> evidence gate
  -> executable action boundary
  -> reviewable compute evidence
```
