# AI Agent Safety & QA — Grant Portfolio

**Maintainer / contributor:** [safal207](https://github.com/safal207)  
**Primary project:** [LS — Cooperative Precision Layer for AI Co-work](https://github.com/safal207/LS)  
**Status date:** 27 June 2026

> QA engineer and open-source researcher building executable conformance tests for safe AI-agent authorization, continuation, memory, causal lineage, and auditability.

## Executive summary

My work focuses on a practical gap in agentic AI systems: an agent action may be operationally successful while still being unauthorized, bound to the wrong intent, resumed against stale state, duplicated, or supported by an incomplete causal chain.

I approach this as a QA and interoperability problem. Instead of relying only on policy prose, I turn safety invariants into:

- machine-readable fixtures;
- positive and negative contract tests;
- deterministic runners;
- framework-neutral conformance profiles;
- CI-enforced regression gates;
- explicit non-claims and human-review boundaries.

The emerging research direction is **Agent Governance Conformance**: small portable test packs that allow agent runtimes, orchestration frameworks, memory systems, and tool gateways to verify the same safety invariant without adopting one vendor's full stack.

## Evidence of external impact

### 1. CrewAI governance contract review

**Artifact:** [CrewAI PR #6030 — GovernanceDecision and GovernanceOutcome contract types](https://github.com/crewAIInc/crewAI/pull/6030)

I reviewed the proposed governance wire contract and identified a boundary problem: because `GovernanceDecision` used `total=False` without route-specific validation, an `allow` decision could be structurally valid while lacking the fields required to verify what action had actually been authorized.

I proposed either:

- a required base contract plus optional extensions; or
- a framework-owned `validate_governance_decision()` enforcing route-specific minimums.

The PR author publicly agreed with the finding and announced a concrete fix: route-specific validation for `allow`, `require_approval`, `deny`, and `revise`.

**Why this matters:** this converts a serialized audit envelope into a safer authorization boundary. It prevents an executable `allow` from being accepted without identity, tool, intent binding, issue time, and policy context.

**Current status:** PR open and mergeable as of 27 June 2026; the proposed fix was acknowledged in the public discussion but should not be described as merged until the PR lands.

### 2. Fail-closed CrewAI governance conformance pack

**Artifacts:**

- [CrewAI Governance Conformance Profile v0.1](../spec/crewai-governance-conformance-v0.1.md)
- [Framework-neutral fixtures and manifest](../fixtures/crewai-governance/)
- [Deterministic fixture runner](../tools/run_crewai_governance_fixtures.py)

After the CrewAI maintainer requested executable fixtures, I produced a framework-neutral contract-test pack covering:

1. exact-intent mismatch;
2. target-state drift and revalidation;
3. continuation mismatch;
4. duplicate successful outcome under the same action reference and idempotency key.

The pack also contains:

- a valid resume control path;
- superseded approval handling;
- incomplete causal-chain coverage;
- an explicit vocabulary-gap analysis for unresolved evidence.

The profile deliberately avoids silently mapping LS `ABSTAIN` to CrewAI `require_approval`. Missing authoritative evidence is not always repairable through human approval, so the profile records the mapping as unrepresentable and proposes a future neutral `defer` verdict.

**Why this matters:** the work makes safety claims falsifiable. Another implementation can consume the same JSON vectors and demonstrate whether it fails closed under intent substitution, stale state, broken continuation, and duplicate side effects.

### 3. Causal audit proposal for CrewAI traces

**Artifact:** [CrewAI issue #6063 — Optional causal audit for agent action traces](https://github.com/crewAIInc/crewAI/issues/6063)

I proposed a narrow optional integration based on [Causal Memory Layer](https://github.com/safal207/Causal-Memory-Layer):

> Given a sequence of agent and tool actions, detect actions that completed operationally but lack a valid parent cause, approval, or responsibility lineage.

The proposal distinguishes ordinary tracing from causal validity:

- tracing records what happened;
- causal audit checks whether an action had a valid permission and responsibility path.

The proposal is intentionally dependency-light, outside CrewAI core, and framed with explicit non-claims rather than as compliance certification.

### 4. LS conformance and continuity architecture

**Artifact:** [LS repository](https://github.com/safal207/LS)

LS is a local-first cooperative precision layer that turns raw AI work into governed artifacts through evidence, continuity checks, consent, route decisions, and human review.

Its conformance direction captures recurring failures such as:

- missed terminal events and bounded reconciliation;
- durable memory being mistaken for authority;
- constrained tool calls reaching upstream without valid credentials;
- pending approval being collapsed into missing approval;
- incomplete record sets being treated as complete authority.

The project currently provides schemas, fixtures, deterministic probes, negative vectors, CI gates, architecture notes, and explicit claim boundaries.

## Core research thesis

Agent safety should not rely only on model behaviour or framework-specific policy code. Critical invariants should be testable across implementations at the serialized contract boundary.

A useful conformance test should answer questions such as:

- Was this exact intent authorized?
- Is the decision still valid for the current target state?
- Does the resumed action belong to the same continuation chain?
- Has this side effect already completed under the same idempotency identity?
- Is remembered information merely context, or does it carry spendable authority?
- Can the decision and outcome be joined and independently verified?
- Is the observed record set demonstrably complete?
- When evidence is insufficient, does the system abstain or accidentally allow?

## Proposed grant project

# Agent Governance Conformance Lab

### Goal

Create an open, framework-neutral conformance suite for testing authorization, continuation, causal lineage, memory boundaries, and audit completeness in AI-agent systems.

### Problem

Agent frameworks increasingly expose hooks, approvals, memory, tools, and execution traces, but safety semantics differ across ecosystems. Teams often have no portable way to prove that the same high-risk scenario fails closed across two runtimes.

### 90-day deliverables

1. **Canonical threat and invariant catalog**
   - exact-intent substitution;
   - target-state drift;
   - continuation mismatch;
   - duplicate side effects;
   - expired or superseded approval;
   - memory-as-authority confusion;
   - incomplete causal chain;
   - tail-drop and incomplete audit records.

2. **Portable conformance format**
   - JSON Schema;
   - accept/reject/revalidate/defer vectors;
   - deterministic expected outcomes;
   - explicit versioning and normalization identifiers.

3. **Reference runners**
   - Python runner;
   - lightweight CLI;
   - CI integration examples;
   - adapter interface for external frameworks.

4. **Two ecosystem adapters**
   - CrewAI governance contracts;
   - one additional open agent runtime or tool gateway.

5. **Evaluation report**
   - which invariants each runtime can represent;
   - lossy vocabulary mappings;
   - false-allow and false-deny findings;
   - reproducible limitations and non-claims.

### Expected outcomes

- a reusable open-source QA benchmark for agent governance;
- lower integration cost for safety testing;
- concrete regression vectors for framework maintainers;
- evidence suitable for academic, public-interest, and open-source grant reporting;
- a bridge between manual QA expertise and agentic-AI safety engineering.

## Differentiation

This work is not another general-purpose observability dashboard and does not claim to make an agent safe by itself.

The distinctive contribution is the conversion of governance ideas into **small executable invariants** that are:

- vendor-neutral;
- fail-closed;
- independently reproducible;
- suitable for CI;
- explicit about missing semantics;
- useful to both maintainers and auditors.

## Grant-ready bio

### 50-word version

Alexey is a QA engineer and open-source contributor working on executable safety tests for AI-agent systems. He builds framework-neutral conformance fixtures for authorization, continuation, causal lineage, memory boundaries, and audit completeness. His CrewAI review work has already influenced the proposed validation design of an active governance contract.

### 100-word version

Alexey is a QA engineer and open-source researcher focused on making AI-agent governance testable rather than purely declarative. Through the LS project, he develops framework-neutral schemas, negative fixtures, deterministic runners, and CI gates for exact-intent binding, stale-state revalidation, safe continuation, idempotency, causal lineage, and memory-authority separation. In CrewAI's active governance-contract work, his review identified that structurally valid `allow` decisions could lack the fields required for safe authorization; the PR author accepted the finding and proposed route-specific validation. His current direction is an open Agent Governance Conformance Lab for cross-runtime regression testing.

## CV / application bullets

- Identified an authorization-boundary flaw in CrewAI's proposed governance contract and proposed route-specific validation; the PR author accepted the finding and announced a framework-level validator.
- Built a framework-neutral CrewAI governance conformance pack with fail-closed fixtures for intent mismatch, target-state drift, continuation mismatch, and duplicate side effects.
- Developed deterministic QA artifacts connecting governance prose to executable JSON fixtures, regression runners, and CI gates.
- Proposed an optional causal-audit integration for agent action traces, distinguishing operational observability from valid permission and responsibility lineage.
- Maintains LS, an open-source cooperative precision and conformance layer for continuity-aware, evidence-bearing, human-reviewable AI work.

## Claim discipline

For grant applications and public profiles, use the following wording carefully:

### Safe to claim now

- Contributed substantive review to an active CrewAI governance PR.
- The PR author explicitly accepted the route-validation finding and proposed a fix.
- Produced an external, framework-neutral conformance pack and deterministic runner.
- Opened and developed a public CrewAI causal-audit proposal.
- Maintains open-source artifacts with testable safety invariants and CI evidence.

### Do not claim yet

- That PR #6030 is merged.
- That CrewAI officially adopted LS or Causal Memory Layer.
- That the conformance pack is an official CrewAI standard.
- That the system provides compliance certification or complete production safety.
- That external impact is proven beyond the public review discussion until code is merged or cited in releases/documentation.

## Evidence links

- CrewAI PR #6030: https://github.com/crewAIInc/crewAI/pull/6030
- CrewAI issue #6063: https://github.com/crewAIInc/crewAI/issues/6063
- LS: https://github.com/safal207/LS
- CrewAI conformance profile: https://github.com/safal207/LS/blob/main/spec/crewai-governance-conformance-v0.1.md
- CrewAI fixtures: https://github.com/safal207/LS/tree/main/fixtures/crewai-governance
- Causal Memory Layer: https://github.com/safal207/Causal-Memory-Layer

## Next evidence milestones

1. Land at least one fixture contribution directly in an upstream agent framework.
2. Obtain a maintainer citation, merged PR, release-note mention, or documentation link.
3. Add a second runtime adapter to demonstrate portability.
4. Publish a small benchmark report with reproducible pass/fail results.
5. Record adoption metrics: external contributors, fixture runs, downstream references, stars, forks, and issue citations.

---

## Коротко по-русски

Это не страница «я интересуюсь CrewAI». Это доказательная карта специализации:

> QA и open-source работа на стыке AI-agent safety, governance, безопасного продолжения, памяти, причинной связности и исполняемых conformance-тестов.

Самый сильный уже подтверждённый результат: замечание по контракту CrewAI было принято автором PR и преобразовано в конкретное архитектурное решение — route-specific validation. Следующая ступень доказательности: upstream merge, второй адаптер и опубликованный сравнительный benchmark.
