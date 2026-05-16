# Grant Reviewer Packet 2026

This packet is a compact reviewer path for the LS / Liminal Stack ecosystem and its connected implementation repositories.

It is written for grant reviewers, technical evaluators, fellowship reviewers, and safety-infrastructure funders who need to understand what exists today, what can be inspected, what is not claimed, and what funding would unlock next.

## One-sentence summary

This is not a bundle of unrelated repositories. It is a connected evidence stack for inspecting human-plus-agent coordination, causal validity, trace continuity, evidence gates, and action boundaries.

```text
LS / Liminal Stack
  -> governance, coordination, continuity, and reviewer surface
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
-> causal authorization
-> trace continuity
-> evidence-gate decision
-> action-boundary decision
-> auditability
```

The current ecosystem tests whether this can be expressed as public repositories, committed fixtures, executable validators, CI checks, reviewer paths, and explicit non-claims.

## What exists today

| Layer | Repository | Evidence available today |
| --- | --- | --- |
| Governance and continuity surface | [LS](https://github.com/safal207/LS) | Council cycles, approval-safe workflows, personal-agent gateway framing, benchmark docs, safety positioning, and this reviewer packet. |
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

Purpose:

```text
Understand the broad governance and reviewer surface.
```

### 2. Inspect the executable hub

Read:

- [ProofPath README](https://github.com/safal207/ProofPath)
- [ProofPath Ecosystem Graph](https://github.com/safal207/ProofPath/blob/main/docs/ECOSYSTEM_GRAPH.md)
- [Compute Witness Grant Reviewer Path](https://github.com/safal207/ProofPath/blob/main/docs/COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md)

Purpose:

```text
Verify that the abstract safety claim has executable artifacts and CI-backed evidence.
```

### 3. Inspect causal validity and replay layers

Read:

- [CML README](https://github.com/safal207/Causal-Memory-Layer)
- [LTP README](https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-)

Purpose:

```text
Understand how causal authorization and trace continuity support the same research direction.
```

## Commands and inspection paths

The exact commands vary by repository, but the current executable review path is centered on ProofPath / Compute Witness.

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
  -> asks whether memory, action, compute, or continuation should be allowed at all
  -> records why it was allowed, blocked, rejected, or held
  -> makes the evidence inspectable and regression-testable
```

The key distinction is not UI polish. It is the shift from:

```text
what did the model say?
```

to:

```text
what evidence allows this output, memory write, compute result, or action to become durable or executable?
```

## Evidence chain

The strongest current evidence chain is:

```text
LS reviewer and governance surface
  -> ProofPath ecosystem graph
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

This evidence chain is narrow, but it is concrete. It gives reviewers artifacts, commands, and expected behavior rather than only a conceptual claim.

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
- full cross-repository replay or dispute resolution;
- full end-to-end production deployment across all layers.

The current claim is narrower and testable:

```text
The ecosystem already contains connected, public, inspectable artifacts for reviewing human-plus-agent coordination, causal validity, trace continuity, evidence gates, action boundaries, and compute-evidence checks.
```

## What funding unlocks next

Funding would harden and connect existing artifacts rather than start from zero.

### Workstream 1: Cross-repo conformance

```text
LS reviewer packet
+ ProofPath evidence hub
+ CML causal validation
+ LTP trace/replay
+ PythiaLabs evidence gates
```

Deliverables:

- shared terminology and reviewer routes;
- compatibility notes between CML, LTP, ProofPath, and Compute Witness;
- small cross-repo demo scenario;
- CI-backed conformance snapshots where feasible.

### Workstream 2: Deeper Rust verification

Deliverables:

- more Compute Witness verification in Rust;
- richer challenge fixture support;
- audit-packet verification beyond the first audit-hash primitive;
- stable CLI outputs for reviewer and pilot usage.

### Workstream 3: Pilot integrations

Deliverables:

- one or two narrow pilot workflows;
- manifest and receipt emission for real agent actions;
- reviewable audit packets;
- short risk notes explaining what passed, failed, and remains unproven.

### Workstream 4: Research and reviewer artifacts

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
  asks whether agent output can become memory, profile state, coordination artifact, or action under human-owned governance.

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
  -> causal authorization
  -> trace continuity
  -> evidence gate
  -> executable action boundary
  -> reviewable compute evidence
```
