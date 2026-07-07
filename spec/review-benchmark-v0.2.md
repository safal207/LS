# Blind Review Benchmark Protocol v0.2 — Frontier-Model Provenance

## Status

Normative protocol for provenance-aware comparison of one externally identified frontier-model run and one LS run over the same frozen exact-head evidence.

v0.2 is additive. It does not rewrite, relabel, or invalidate preserved v0.1 runs.

## Motivation

Two real intake failures exposed a missing trust boundary in v0.1:

1. a Gemini response copied the case digests but violated the report contract and invented entities absent from the frozen bundle;
2. a Grok response passed the v0.1 report shape but declared itself to be Claude 3.5 Sonnet.

A valid JSON report is therefore not sufficient evidence of reviewer identity. Model output cannot be the authority for model provenance.

## Core invariant

```text
model self-identification
!= executor provenance
```

Executor identity is created outside the model response in an immutable `RunBinding` before invocation.

```text
frozen case
+ exact prompt bytes and digest
+ external executor identity
+ provenance level
+ run ID
+ nonce
        ↓ canonical SHA-256
run_binding_sha256
        ↓ copied by model
report
        ↓ semantic validation
seal
```

The model report contains no `reviewer`, `provider`, `system`, `model`, or `version` field.

## Lanes

v0.2 uses exactly two lanes:

- `FRONTIER_MODEL`;
- `LS`.

The protocol does not pretend that Gemini, Grok, Claude, or another model is interchangeable with the `FRONTIER_MODEL` lane by name alone. The authoritative executor is recorded in the lane's external run binding.

## Provenance levels

### `USER_ATTESTED`

A human operator records the web-UI or local executor identity before model output. This is explicit but not cryptographically verified by the provider.

### `API_VERIFIED`

The runner records identity from an API invocation under its controlled request/response metadata. This level requires `executor.channel = API`.

### `WORKFLOW_VERIFIED`

A trusted workflow records identity and run metadata. This level requires `executor.channel = WORKFLOW`.

A model cannot upgrade provenance. The scorecard must display the provenance level alongside performance metrics.

## Run binding

A `ls.review_benchmark_run_binding.v0.2` object binds:

- case ID;
- lane;
- frozen evidence SHA-256;
- prompt SHA-256;
- unique run ID;
- executor provider, model, version, and channel;
- provenance level, issuer, and evidence;
- a 256-bit nonce.

The frozen case records both `prompt_path` and `prompt_sha256`. Before a binding, report, seal, or scorecard is accepted, the reference runtime reads the prompt bytes below the repository root, recomputes SHA-256, and requires equality with the case digest. The binding prompt digest must then equal the case prompt digest.

The canonical JSON SHA-256 of the run binding is `run_binding_sha256`.

Any mutation to executor identity, provenance, run ID, nonce, evidence digest, or prompt digest produces a different binding hash and invalidates the report.

## Report contract

A v0.2 report copies exactly:

- `case_id`;
- `lane`;
- `evidence_sha256`;
- `prompt_sha256`;
- `run_binding_sha256`.

The report must not contain model identity fields. Additional properties fail closed.

Finding IDs are lane-specific:

- frontier model: `FM-*`;
- LS: `LS-*`.

`REPRODUCED` and `STATICALLY_PROVEN` findings require at least one concrete reproduction step.

LS retains mandatory non-empty artifact nodes, relations, and probes. Frontier-model structured arrays may be empty. Every proposed edge must reference source and target nodes declared in that report's `artifact_nodes`.

## Sealing

The v0.2 seal semantically binds:

- report hash;
- external run-binding hash;
- run ID;
- executor identity;
- provenance level;
- evidence and prompt hashes;
- finding and proposed-edge identities.

Changing the binding after report generation invalidates both report acceptance and seal validation.

## Adjudication and scorecard

v0.2 preserves human adjudication, conditional recall, precision, reproduction rate, escalation quality, attribution accuracy, severity accuracy, overlap analysis, and governed edge proposals.

Lane-specific categories are:

- `BOTH_TRUE`;
- `FRONTIER_MODEL_ONLY_TRUE`;
- `LS_ONLY_TRUE`;
- `FALSE_POSITIVE`;
- `EVIDENCE_GAP`;
- `DUPLICATE_FINDING`;
- `HUMAN_DECISION_REQUIRED`;
- `OUT_OF_SCOPE`.

The scorecard records each lane's executor object and provenance level. A `USER_ATTESTED` result may be compared, but must never be presented as API-verified. Per-lane outcome counters include duplicate findings so every report finding remains visible in the scorecard.

## Negative controls

The reference runtime rejects:

- a report that adds `reviewer` or other self-identity fields;
- a report that calls itself `LS` under a frontier-model binding;
- a report whose binding hash was copied incorrectly;
- a case whose declared prompt digest does not match the prompt bytes;
- a binding whose prompt digest differs from the frozen case;
- a report evaluated against a binding whose model identity changed after generation;
- `API_VERIFIED` provenance on a non-API channel;
- `WORKFLOW_VERIFIED` provenance on a non-workflow channel;
- `CLAUDE-*` finding IDs in the frontier-model lane;
- an LS report without graph structures and probes;
- a proposed edge whose source or target node is absent;
- a proven reproduction claim with no reproduction steps;
- whitespace-only semantic text;
- a seal evaluated against mutated provenance;
- incomplete finding or edge adjudication.

Malformed JSON and non-UTF-8 JSON inputs fail closed as `BenchmarkV02Error` rather than escaping as unhandled parser exceptions.

## Migration boundary

Preserved v0.1 Gemini and Grok attempts remain immutable negative-control artifacts. They must not be edited and relabeled as v0.2 reports.

A valid v0.2 run requires a new run ID, new nonce, v0.2 prompt, external run binding, fresh model response, and fresh seal over the same frozen evidence bytes.

## Authority boundary

Neither a run binding, report, seal, adjudication, nor scorecard grants approval, merge authority, execution authority, or trusted graph mutation authority.
