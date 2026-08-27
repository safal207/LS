# LS Agent Trust Runtime v0.1 — External Review Packet

## Purpose

This packet asks independent reviewers to attack a narrow trust layer built around the OpenAI Agents SDK.

The prototype does **not** claim to authenticate agents, validate evidence content, execute external effects, or provide production authorization. It tests a smaller question:

> Can a multi-agent workflow preserve verifiable delegation, recovery freshness, evidence binding, and human authority separation without replacing the underlying agent framework?

## Review target

Repository: `safal207/LS`

Prototype path:

```text
prototypes/openai-agent-trust-runtime/
```

Reviewed baseline commit:

```text
1e51b10240d2ea44a147aea577a1612e608719ea
```

Primary files:

```text
src/ls_agent_trust/runtime.py
src/ls_agent_trust/openai_demo.py
tests/test_runtime.py
docs/architecture.md
docs/threat-model.md
```

## Ten-minute reproduction

```bash
git clone https://github.com/safal207/LS.git
cd LS
git checkout 1e51b10240d2ea44a147aea577a1612e608719ea
cd prototypes/openai-agent-trust-runtime
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
ls-agent-trust-demo --dry-run
```

The dry run makes no API calls and does not execute merge, deploy, payment, messaging, deletion, or any other external effect.

## Architecture under review

```text
Human
  ↓
Coordinator Agent
  ↓ typed handoff + parent allowlist
Developer Agent
  ↓ typed handoff + parent allowlist
QA Agent
  ↓ typed handoff + parent allowlist
Safety Reviewer
  ↓ evidence-bound result receipt
Protected-effect gate
  ├── no exact human approval → BLOCK
  └── exact approval for exact result → ALLOW policy decision only
```

The OpenAI Agents SDK remains responsible for model execution, handoffs, tools, sessions, and tracing. LS adds a separate deterministic trust ledger.

## Intended invariants

1. **Named-child binding** — only the child named in a dispatch may submit its terminal result.
2. **Evidence presence** — `COMPLETED` requires at least one evidence reference.
3. **One terminal result** — a dispatch cannot submit multiple terminal outcomes.
4. **Recovery freshness** — recovery creates a new dispatch and makes the predecessor stale.
5. **No recovery escalation** — recovery must preserve task, constraints, and authority scope.
6. **Parent authority ceiling** — model-requested handoff authority must be a subset of the parent-configured allowlist.
7. **Protected-effect normalization** — effect identifiers are normalized before scope and approval checks.
8. **Result-bound approval** — approval can be created only after a completed result and is bound to that exact result receipt.
9. **No implicit execution** — `allowed=true` is a policy decision, never execution of an effect.
10. **Observed-sequence integrity** — mutation, insertion, or reordering inside the supplied ledger sequence is detectable.

## Explicit non-claims

The prototype does not provide:

- cryptographic process, model, container, agent, or human identity;
- evidence truth, provenance, malware, or completeness verification;
- durable storage, consensus, or exactly-once effect execution;
- external timestamping or signed ledger checkpoints;
- suffix-truncation detection without an external checkpoint;
- prompt-injection prevention;
- runtime sandboxing or tool isolation;
- transactional binding between policy approval and a real effect adapter;
- proof that a live OpenAI API run completed safely;
- endorsement by OpenAI or OWASP.

## Requested attack scenarios

Please attempt to produce a minimal proof of concept for any of the following:

1. Submit a result as an agent other than the dispatched child.
2. Reuse a result receipt across two dispatches.
3. Submit late work from an agent after its dispatch was superseded.
4. Recover a task while relaxing constraints or expanding authority.
5. Request authority outside a parent handoff allowlist.
6. Bypass a protected effect using case, whitespace, Unicode, or naming ambiguity.
7. Create an approval before a completed result exists.
8. Reuse an approval for a different result or effect.
9. Cause an incomplete or interrupted SDK run to be represented as `COMPLETED`.
10. Tamper with, reorder, insert into, or truncate the ledger without detection.
11. Exploit model-generated handoff metadata to create a misleading receipt.
12. Turn an `ALLOW` policy decision into an unintended real-world effect through integration assumptions.

## Questions for reviewers

1. What is the highest-severity bypass of the intended invariants?
2. Which invariant is underspecified or impossible to enforce at this layer?
3. What minimum cryptographic identity or signing scheme should v0.2 add?
4. Should receipts correlate through SDK trace/span identifiers, application-generated run IDs, or both?
5. What is the correct durable protocol for approval, idempotency, effect request, and execution receipt?
6. Which external ledger checkpoint design gives useful truncation detection without overengineering the prototype?
7. Which security property belongs in the OpenAI Agents SDK integration layer versus application policy?

## OWASP Agentic Top 10 mapping

This is a partial mapping, not a compliance claim.

| OWASP risk | Prototype relevance | Current boundary |
|---|---|---|
| ASI02 — Tool Misuse & Exploitation | Authority scopes and protected-effect gates reduce direct misuse | No tool sandbox or real effect adapter |
| ASI03 — Identity & Privilege Abuse | Named-child checks and parent authority ceilings constrain labels | Agent and human identities are not cryptographically authenticated |
| ASI06 — Memory & Context Poisoning | Ledger separates recorded receipts from free-form memory | Memory content and prompt injection are not inspected |
| ASI07 — Insecure Inter-Agent Communication | Dispatch and result receipts bind sender, receiver, task, and lineage | Transport authenticity and confidentiality are not provided |
| ASI08 — Cascading Failures | Supersession blocks stale workers after recovery | No distributed failure containment or consensus |
| ASI09 — Human-Agent Trust Exploitation | Protected actions require separate exact-result approval | Human identity, UI deception, and approval quality are not solved |
| ASI10 — Rogue Agents | Out-of-scope and unapproved effects fail closed in the policy layer | A rogue process controlling the host remains outside the threat model |

## Preferred review output

A useful response can be short. Please provide:

1. finding title and severity;
2. violated invariant;
3. minimal reproduction or failing test;
4. expected versus actual behavior;
5. OWASP mapping where applicable;
6. smallest safe remediation;
7. whether the issue blocks a public demonstration.

## Suggested OpenAI Agents SDK discussion

**Title**

```text
Show and tell: evidence-bound handoffs, recovery lineage, and human authority gates
```

**Opening**

```text
We built a small Apache-2.0 trust layer around the OpenAI Agents SDK rather than another orchestration framework. Typed handoff callbacks create deterministic dispatch receipts. Terminal results are bound to the named child and require evidence references. Recovery supersedes stale work. Model-requested authority is capped by a parent allowlist, and protected effects require a separate human approval bound to the exact completed result.

We would value critical feedback on three integration questions:

1. What is the best SDK seam for correlating external dispatch receipts with trace/span IDs?
2. How should a resumable handoff express that its predecessor is permanently stale?
3. Is a small vendor-neutral receipt schema useful to the SDK ecosystem, or should this remain application-level policy?

Review packet and reproduction steps:
https://github.com/safal207/LS/blob/main/prototypes/openai-agent-trust-runtime/EXTERNAL_REVIEW_PACKET.md
```

## Suggested OWASP review request

**Title**

```text
Request for adversarial review: evidence-bound multi-agent delegation and human authority gate
```

**Opening**

```text
We are requesting a narrow, public adversarial review of an Apache-2.0 multi-agent trust prototype. The implementation focuses on dispatch integrity, stale-worker rejection after recovery, parent-side authority ceilings, result-bound human approval, and a tamper-evident local ledger.

We are not requesting certification or endorsement. We want reviewers to identify bypasses and map them to the OWASP Top 10 for Agentic Applications, especially ASI02, ASI03, ASI07, ASI08, ASI09, and ASI10.

The packet contains a ten-minute offline reproduction, explicit non-claims, attack scenarios, and a preferred finding format:
https://github.com/safal207/LS/blob/main/prototypes/openai-agent-trust-runtime/EXTERNAL_REVIEW_PACKET.md
```

## Disclosure

This repository is public. Please do not include credentials, private data, or unrelated third-party vulnerabilities in review comments. For a vulnerability that could affect another live system, follow that project's responsible-disclosure process rather than posting exploit details here.
