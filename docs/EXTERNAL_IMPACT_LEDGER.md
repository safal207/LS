# External Impact Ledger

## Purpose

This ledger records public technical contributions and review signals from external AI-agent runtime projects. It is intended as a portfolio and evidence trail for work at the boundary of QA, systems analysis, AI-agent governance, approval lifecycle, causal audit, permission enforcement, and runtime verification.

The core theme is:

> AI agents should not only perform actions; they should prove that each action had valid authority, valid cause, valid state, and valid execution boundaries.

---

## Case 1 — [crewAI #6030](https://github.com/crewAIInc/crewAI/pull/6030): GovernanceDecision / GovernanceOutcome contract

**Project:** crewAI

**Area:** AI-agent governance, runtime authorization, pre-/post-execution contracts.

**Public evidence:** review discussion, contract feedback, and contributed fail-closed fixture design are preserved in [crewAI PR #6030](https://github.com/crewAIInc/crewAI/pull/6030).

### What happened

A public PR introduced `GovernanceDecision` and `GovernanceOutcome` contract types for agent tool-call governance. The contract separates pre-execution authorization from post-execution outcome and supports vendor-neutral evidence through extensions.

### Technical focus

- Pre-execution decision vs post-execution outcome separation.
- Intent binding.
- Idempotency and duplicate execution prevention.
- `intent_ref` as a stable semantic identity.
- `idempotency_key` as retry/duplicate boundary.
- `normalization_id` as the recomputation rule for executable intent.
- Runtime-verifiable governance records.
- Avoiding the mistake where a decision record pretends to prove execution.

### Key invariant

```text
GovernanceDecision is not GovernanceOutcome.

A pre-execution decision may authorize an action,
but only a post-execution outcome can prove what actually happened.
```

### Why it matters

This prevents a common AI-agent runtime failure:

```text
The system says “allowed”
but cannot prove:
- what exact action was allowed;
- whether the same action was executed twice;
- whether the executed action still matched the approved intent;
- whether the result belongs to the original decision.
```

### Portfolio value

This is a strong public technical review case in AI-agent governance and runtime verification.

### Resume wording

Contributed public technical review around an open-source AI-agent governance PR, focusing on pre-/post-execution contract separation, intent binding, duplicate execution prevention, idempotency boundaries, and runtime-verifiable decision/outcome records.

---

## Case 2 — [crewAI #6063](https://github.com/crewAIInc/crewAI/issues/6063): Causal Memory Layer proposal for agent action traces

**Project:** crewAI + Causal Memory Layer

**Area:** causal audit, agent trace validation, responsibility lineage.

**Public evidence:** the proposal, follow-up artifacts, and external validation trail are preserved in [crewAI issue #6063](https://github.com/crewAIInc/crewAI/issues/6063).

### What happened

A proposal was opened for an optional integration idea around `causal-memory-layer`, a Python package for checking causal validity in structured agent action traces.

The proposal asks whether CrewAI workflows could be converted into causal records and audited for broken parent cause, approval, or responsibility lineage.

### Technical focus

```text
Given a sequence of agent/tool actions,
can we detect actions that succeeded operationally
but lack a valid parent cause, approval, or responsibility lineage?
```

### Key invariant

```text
Operational success is not the same as causal validity.
```

An agent action can complete successfully but still be invalid if it has no valid upstream cause, approval, or responsibility chain.

### Why it matters

Normal tracing answers:

```text
What happened?
```

Causal audit asks:

```text
Was this action allowed to happen,
and did it have a valid reason, parent, or authority path?
```

### Portfolio value

This is a direct public OSS proposal connected to a package and shows product plus architecture thinking.

### Resume wording

Proposed a causal audit integration for AI-agent workflows, using structured action traces to detect missing or malformed parent cause, approval, and responsibility lineage beyond ordinary observability/tracing.

---

## Case 3 — [OpenAI Codex #29627](https://github.com/openai/codex/issues/29627): Durable approval lifecycle and AuthorityState boundary

**Project:** OpenAI Codex

**Area:** approval lifecycle, user authority, durable runtime state.

**Public evidence:** the state-machine analysis and linked LS conformance artifacts are preserved in [OpenAI Codex issue #29627](https://github.com/openai/codex/issues/29627).

### What happened

A Codex issue described a failure where pending manual approvals could be automatically cancelled or treated as missing/unapproved when the agent stopped waiting.

The contribution framed this as a durable approval-state problem and a boundary between requester state and authority state.

### Technical focus

- Pending approval as first-class runtime state.
- Avoiding collapse of `PENDING` into `DENIED`.
- Preventing an agent from resolving its own approval request.
- Binding execution to an approval id and action digest.
- Preserving approval state across restart, compaction, resume, and UI refresh.
- Blocking semantically equivalent alternative actions when the same authority is required.

### Key invariant

```text
Pending approval is not rejection.

The requesting agent must not convert:
PENDING → DENIED
PENDING → CANCELLED
PENDING → APPROVED
```

Only the user, an explicit expiry policy, or a valid context invalidation should resolve the approval.

### Why it matters

This prevents a dangerous agent-runtime bug:

```text
The agent asks for permission.
The user has not answered yet.
The agent stops waiting.
The system treats that as “permission denied” or “approval missing”.
```

That is not a valid authority transition.

### Portfolio value

This is a strong systems-analysis case about state machines, authority lifecycle, approval durability, and conformance fixtures.

### Resume wording

Analyzed an AI-agent approval lifecycle bug and proposed a durable approval state model separating requester state from user authority state, including conformance fixtures for pending approvals, explicit resolution, action binding, restart/resume preservation, and replay prevention.

---

## Case 4 — Claude Code [#30519](https://github.com/anthropics/claude-code/issues/30519) / [#76149](https://github.com/anthropics/claude-code/issues/76149): Effective permission vs configured permission

**Project:** Anthropic Claude Code

**Area:** permission enforcement, allow/deny rules, Auto Mode, MCP tool authorization.

**Public evidence:** normalized-command intent analysis appears in [Claude Code issue #30519](https://github.com/anthropics/claude-code/issues/30519); the related Auto Mode/MCP allowlist failure is documented in [issue #76149](https://github.com/anthropics/claude-code/issues/76149).

### What happened

Claude Code issues describe cases where configured permissions and effective runtime behavior diverge. Allowlist rules may not match compound commands reliably, and Auto Mode can block allowlisted MCP calls.

### Technical focus

```text
Configured permission is not the same as effective executable authority.
```

A rule may exist in settings, but runtime still needs to prove:

- the command matched correctly;
- compound commands were decomposed correctly;
- deny rules still hold under syntax variation;
- Auto Mode/classifier decisions do not silently override clear user authority;
- tool execution matches the configured authority boundary.

### Key invariant

```text
Permission must be executable, not decorative.
```

If a permission rule cannot reliably allow or deny the action at runtime, it is not a real control.

### Why it matters

This is a core AI-agent governance issue:

```text
A system can look safe on paper
while still being unsafe or unusable in execution.
```

### Portfolio value

This supports a broader portfolio narrative around runtime verification and effective authority.

### Resume wording

Mapped permission enforcement failures in AI-agent developer tools into an effective-authority model, distinguishing configured permissions from runtime-executable authority and identifying risks in allowlists, compound command matching, Auto Mode classifiers, and MCP tool authorization.

---

## Core Pattern Library

### Pattern 1 — Decision is not outcome

```text
A decision says what may happen.
An outcome says what did happen.
They must be separate records.
```

### Pattern 2 — Pending is not denied

```text
Waiting for user approval is not failure, denial, or cancellation.
```

### Pattern 3 — Configured permission is not effective authority

```text
A permission rule in settings is only useful if runtime enforcement actually follows it.
```

### Pattern 4 — Operational success is not causal validity

```text
An action can complete successfully but still lack valid cause, approval, or responsibility lineage.
```

### Pattern 5 — The agent must not be the system of record

```text
Anything load-bearing for safety, approval, audit, or authority must live outside the agent and must not be authored only by the agent.
```

---

## Portfolio Summary

I work at the boundary between QA, systems analysis, and AI-agent runtime governance.

My public technical contributions focus on identifying hidden failure modes in AI-agent systems, especially where actions, approvals, permissions, traces, and outcomes become incorrectly mixed.

I translate those risks into testable invariants, state-machine boundaries, contract fields, and conformance scenarios that can be used by engineering teams to improve reliability and safety.

---

## Short Resume Version

Publicly contributed technical reviews and proposals to open-source AI-agent runtime projects, focusing on governance contracts, approval lifecycle, causal audit, intent binding, idempotency, permission enforcement, and runtime verification.

Identified and articulated failure modes including duplicate execution bypass, weak intent binding, pending approval state collapse, mismatch between configured permissions and effective runtime authority, and missing causal responsibility lineage.

---

## LinkedIn / Portfolio Headline

AI Agent Runtime QA / Governance Reviewer  
Systems Analyst focused on approval lifecycle, permission enforcement, causal audit, and runtime verification for autonomous agent systems.
