---
name: Internet CI Epic
title: "Epic: Internet CI / CI Node Mesh"
labels: epic, ci-memory, agent-runtime
assignees: ''
---

# Epic: Internet CI / CI Node Mesh

## Vision

Build an Internet of CI Nodes: a distributed agent memory and execution mesh where repositories share context, evidence, best routes, anti-patterns, and CI-backed experiments.

This is not a blockchain replacement in general. It is better than blockchain for this project’s current needs: agent memory, CI experiments, cross-repository experience sharing, and reproducible engineering evidence.

## Core thesis

```text
Blockchain = trust machine
CI Mesh = execution + evidence machine
```

For LS we need:

- agent execution;
- memory;
- replay;
- causal graph;
- best routes;
- experiments;
- cross-repository experience transfer.

## Why CI Mesh instead of blockchain first

Blockchain is useful when the main problem is:

- many parties do not trust each other;
- a shared immutable ledger is required;
- consensus is required;
- tokens or economic incentives are required.

LS currently needs:

- agents working with code;
- CI running tests and reviews;
- repositories storing experience;
- evidence in logs, artifacts, comments, and summaries;
- fast experiment cycles.

GitHub and CI already provide most of this:

```text
Git = history
CI = computation
Artifacts = evidence
Comments = interface
Context exports = agent memory
```

## Key formula

```text
Blockchain records what was written.
CI Mesh proves what was checked, why, by whom, on which code, and which route worked.
```

## Architecture draft

```text
Repository
  -> CI Node
  -> Command Bus
  -> Workflow Runtime
  -> Evidence Artifacts
  -> Agent Context Export
  -> Shared Route Memory
```

Node types:

- memory node;
- review node;
- experiment node;
- product node;
- verification node;
- route-learning node.

## Backlog

### Phase 1 — Local CI Node foundation

- [ ] Define CI node manifest schema.
- [ ] Add `.ci_nodes/registry.json`.
- [ ] Add node entries for Grok review, CI memory, and Robys/product nodes.
- [ ] Define command bus contract.
- [ ] Define ack/result marker convention.
- [ ] Define node authority boundaries: advisory only, evidence only, merge authority, etc.

### Phase 2 — CI Memory Exchange

- [ ] Add `.ci_exchange/` directory.
- [ ] Define schemas for context, route, anti-pattern, scorecard, and evidence bundle.
- [ ] Export `connector-safe-command-bus.context.json`.
- [ ] Export `grok-review-command-bus.route.json`.
- [ ] Export `connector-issue-comment-trigger.antipattern.json`.
- [ ] Add confidence and applicability boundaries to every exported claim.

### Phase 3 — Agent context exports

- [ ] Generate `agent_context.latest.json` from CI memory and review evidence.
- [ ] Include known working routes.
- [ ] Include known bad routes.
- [ ] Include unresolved blockers.
- [ ] Include next recommended action.
- [ ] Add deterministic tests for context export.

### Phase 4 — Cross-repository sharing

- [ ] Allow external repositories to import context packs.
- [ ] Add source repo, source commit, confidence, evidence count, and applicability scope.
- [ ] Add route reuse scorecard.
- [ ] Add feedback loop where external repos export whether a route worked.
- [ ] Add examples for Robys and LS.

### Phase 5 — Optional blockchain anchoring later

- [ ] Define hash checkpoint format for important evidence bundles.
- [ ] Decide which artifacts are worth anchoring.
- [ ] Keep rich memory in GitHub/CI; anchor only compact hashes if needed.

## Safety principles

- A node must not grant itself authority.
- Memory node is not merge authority.
- Review node is advisory unless explicitly promoted by a human.
- Experiment node must not deploy production.
- Imported context is evidence, not truth.
- Every claim must include confidence and applicability boundaries.

## Acceptance criteria

- A repo can describe its CI nodes in a machine-readable registry.
- A repo can export reusable route/context/anti-pattern memory.
- Another repo or agent can import that memory and use it as advisory context.
- Every exported claim includes evidence references and validity boundaries.
- CI remains the execution and evidence layer; blockchain is optional anchoring only.
