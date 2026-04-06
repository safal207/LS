# LS Ideal Customer Profile (ICP)

## ICP thesis

LS should first sell into organizations where:
- coordination mistakes are expensive,
- decision processes are review-heavy,
- explainability is mandatory,
- generic agents feel too unbounded for governance.

---

## Segment A: Fintech / compliance-heavy product teams

### Core pain
- Release and change decisions involve product, risk, compliance, legal, and operations.
- Teams have plenty of data but weak shared interpretation of readiness.
- Last-mile disagreements delay decisions and create rework.

### Why they buy
- Need compact, explainable advisory outputs for go/no-go discussions.
- Need traceability for internal governance and external audits.
- Need a consistent language across technical and non-technical reviewers.

### Why they cannot simply replace LS
- Dashboards show signals but not strategy-to-scene fit.
- Generic agents summarize text but often lack bounded coordination contracts.
- Manual review-only workflows are too slow and inconsistent.

### Why generic agent is insufficient
- Outputs can be prompt-fragile and hard to standardize across teams.
- Confidence is often implicit rather than schema-bound.
- Review bodies need deterministic, comparable advisory fields.

---

## Segment B: High-stakes release coordination orgs

### Core pain
- Cross-functional launches break on alignment, not on pure execution.
- Urgency pressures teams to act before stabilization.
- Postmortems repeatedly cite unclear risk ownership and poor handoffs.

### Why they buy
- Faster and clearer release readiness framing.
- Explicit top risk driver before committing to action.
- Better coordination handoffs between product, engineering, and operations.

### Why they cannot simply replace LS
- PM tooling tracks tasks, not coordination state quality.
- Standup rituals do not produce reusable advisory objects.
- Generic copilots do not reliably model multi-party tension dynamics.

### Why generic agent is insufficient
- Broad assistants optimize for helpfulness, not coordination fit accuracy.
- Inconsistent wording leads to alignment drift between teams.
- Hard to benchmark and contract-test free-form outputs.

---

## Segment C: Review-heavy multi-agent pipelines

### Core pain
- Multiple agents produce outputs, but human reviewers lack a compact trust layer.
- Decision latency grows with every additional review stage.
- Teams struggle to prioritize interventions when outputs conflict.

### Why they buy
- LS provides a stable coordination summary object for reviewer handoff.
- Reduced cognitive load: reviewers focus on explicit risk and readiness fields.
- Easier governance for AI-assisted workflows.

### Why they cannot simply replace LS
- Orchestration systems route tasks but do not provide scene-fit advisory semantics.
- Human-only arbitration does not scale with pipeline throughput.

### Why generic agent is insufficient
- General LLM answers are often non-uniform across similar cases.
- Multi-review environments require predictable output shape and rationale.

---

## Segment D: Legal / audit / governance contexts

### Core pain
- High requirement for explainability and procedural consistency.
- Decisions must be justified and reconstructed later.
- Cross-team interpretation gaps create audit friction.

### Why they buy
- LS outputs are compact, explicit, and easier to evidence.
- Supports governance-first operating model without full automation risk.
- Improves quality of review packets and meeting decisions.

### Why they cannot simply replace LS
- Traditional policy docs are static and hard to operationalize live.
- Generic assistants do not automatically meet evidentiary structure requirements.

### Why generic agent is insufficient
- Narrative-only outputs are hard to compare across decisions.
- Audit scenarios need stable fields, not only persuasive prose.

---

## Buying triggers (cross-segment)

- Increased incident cost from coordination failures.
- Regulatory or internal governance pressure.
- Rapid adoption of AI tooling with weak review consistency.
- Leadership mandate to improve decision quality without slowing velocity.

## Initial exclusion criteria

Do not prioritize customers where:
- coordination risk is low,
- decisions are reversible and cheap,
- auditability is not important,
- primary need is simple task automation.

## First 3 customer conversations: desired outcomes

- Validate top two pains per segment.
- Confirm what "decision-ready" means in their workflow.
- Quantify baseline cost of mis-coordination (delay, rework, risk exposure).
- Map required advisory fields for successful internal adoption.
