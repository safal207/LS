# Devpost submission package

## Project name

LS — Qwen Autopilot Trust Agent

## Tagline

A fail-closed trust gateway that lets autonomous business agents move fast without silently crossing financial, production, credential, or irreversible safety boundaries.

## Track

Track 4: Autopilot Agent

## Submission status

- [x] Public open-source repository
- [x] Apache-2.0 license in the parent repository
- [x] Qwen Cloud integration
- [x] Deterministic safety policy
- [x] Human-in-the-loop approval queue
- [x] Architecture diagram
- [x] Docker deployment assets
- [x] Automated policy and API smoke tests
- [ ] Public Alibaba Cloud deployment URL
- [ ] Deployment evidence with a real `qwen.status = COMPLETED` response
- [ ] Public demo video under three minutes
- [ ] Final screenshots and Devpost submission

## Inspiration

Autonomous agents are becoming capable enough to send customer messages, deploy code, change production data, access credentials, and initiate financial workflows. The dangerous gap is not raw model intelligence. It is the moment between an agent proposing an action and the outside world accepting that action as authorized.

LS adds that missing control point. Every proposed action is evaluated by two independent layers: Qwen Cloud provides contextual risk reasoning, while a deterministic policy defines a non-negotiable safety floor. The strictest result wins.

## What it does

LS accepts a proposed business action and returns one of three decisions:

- `ALLOW` for low-risk, reversible, internal actions.
- `HUMAN_APPROVAL` for meaningful external effects, incomplete evidence, or uncertainty.
- `BLOCK` for destructive or critically unsafe actions.

The result includes risk level, confidence, reasons, required controls, deterministic policy signals, Qwen execution status, and an explicit execution boundary. Actions requiring review are stored in a human approval queue and can be approved or rejected with an auditable reviewer record.

The service never claims that an action was executed. It is a trust and authorization layer, not a hidden executor.

## How we built it

- FastAPI service and interactive browser demo.
- Qwen Cloud through Alibaba Cloud Model Studio's OpenAI-compatible API.
- `qwen3.7-plus` for semantic risk reasoning.
- Deterministic Python policy floor for irreversible, financial, credential, production, privacy, and external side effects.
- Strict decision combiner so model output cannot weaken the policy floor.
- Pydantic validation for Qwen's structured assessment.
- SQLite approval queue with WAL mode and explicit idempotent resolution behavior.
- Docker packaging for Alibaba Cloud deployment.
- Pytest policy tests and end-to-end API smoke tests in GitHub Actions.

## Architecture

The architecture diagram is in [`docs/architecture.md`](docs/architecture.md).

Flow:

1. An AI agent proposes an action.
2. FastAPI sends the same evidence to the deterministic policy and Qwen Cloud.
3. Qwen reasons about context and ambiguity.
4. The deterministic layer establishes the minimum safe decision.
5. The strictest decision wins.
6. Human-review cases enter an auditable approval queue.
7. The response explicitly says `NOT_EXECUTED` because judgment is not execution authority.

## Challenges we ran into

The central challenge was making useful model reasoning compatible with a hard safety guarantee. A language model can understand ambiguous context, but its response may be malformed, unavailable, or too permissive. We therefore designed the system so that Qwen adds semantic judgment without becoming a single point of authorization.

We also had to make failure visible. Missing credentials, timeouts, and invalid model output become `HUMAN_APPROVAL` rather than a silent allow. Approval resolution is explicit and idempotent, so a second reviewer cannot silently overwrite a completed decision.

## Accomplishments that we're proud of

- Qwen reasoning cannot weaken deterministic safety policy.
- Model failure is fail-closed and visible.
- Every response separates assessment from execution authority.
- Human approval decisions are persisted with reviewer evidence.
- The project runs as a small deployable service rather than a notebook-only demo.
- CI tests both policy behavior and HTTP-level API behavior.

## What we learned

Reliable agents need more than better prompts. They need explicit authority boundaries, deterministic fallback behavior, structured output validation, and evidence that can be inspected after a decision. Human-in-the-loop is most useful when it is a first-class state in the workflow rather than an emergency button added at the end.

## What's next

- Replace the local approval store with a managed regional database.
- Add signed, short-lived authorization tokens after human approval.
- Integrate Slack, GitHub, email, and deployment tools behind the gateway.
- Add organization-specific policies and risk budgets.
- Store immutable decision evidence for compliance and incident review.
- Compare agent completion rate and unsafe-action rate against a single-model baseline.

## Testing instructions

### Public demo

Replace this placeholder before submission:

`https://<PUBLIC-ALIBABA-CLOUD-URL>/`

### Health check

```bash
curl -s https://<PUBLIC-ALIBABA-CLOUD-URL>/healthz
```

Expected:

```json
{"status":"ok","service":"ls-qwen-autopilot-agent"}
```

### Low-risk scenario

Use the browser demo or call `/api/evaluate` with a read-only internal action. Confirm:

- `decision = ALLOW`
- `qwen.status = COMPLETED`
- `execution.status = NOT_EXECUTED`

### Human-review scenario

Submit an external customer email or financial workflow. Confirm:

- `decision = HUMAN_APPROVAL`
- an `approval_id` is returned
- the approval can be reviewed through the approval API

### Block scenario

Submit an irreversible production deletion without verified backup. Confirm:

- `decision = BLOCK`
- deterministic policy signals include destructive and production risk
- Qwen cannot reduce the final decision

## Required repository links for the Devpost form

Replace `<BRANCH_OR_COMMIT>` with the final immutable commit SHA.

- Source directory: `https://github.com/safal207/LS/tree/<BRANCH_OR_COMMIT>/hackathons/qwen-autopilot-agent`
- Qwen Cloud API integration: `https://github.com/safal207/LS/blob/<BRANCH_OR_COMMIT>/hackathons/qwen-autopilot-agent/app/qwen.py`
- Architecture diagram: `https://github.com/safal207/LS/blob/<BRANCH_OR_COMMIT>/hackathons/qwen-autopilot-agent/docs/architecture.md`
- Docker deployment path: `https://github.com/safal207/LS/blob/<BRANCH_OR_COMMIT>/hackathons/qwen-autopilot-agent/Dockerfile`
- Deployment evidence: `https://github.com/safal207/LS/blob/<BRANCH_OR_COMMIT>/hackathons/qwen-autopilot-agent/docs/DEPLOYMENT_EVIDENCE.md`

## Demo video script — target 2:35

### 0:00–0:18 — Problem

"Autonomous agents can now send messages, deploy code, change data, and move money. But model confidence is not authorization. LS is a trust gateway between an agent's proposal and real-world side effects."

### 0:18–0:38 — Architecture

Show the diagram.

"Every action goes to Qwen Cloud for contextual reasoning and to a deterministic safety policy. The strictest decision wins. Qwen can make a result stricter, but never weaker."

### 0:38–1:02 — ALLOW

Run the read-only report scenario.

Point to:

- `ALLOW`
- Qwen status `COMPLETED`
- confidence and reasons
- execution status `NOT_EXECUTED`

### 1:02–1:34 — HUMAN_APPROVAL

Run the customer email or payment scenario.

Show the generated approval ID, then approve it as a human reviewer. Explain that the decision is persisted and cannot be silently overwritten by a second review.

### 1:34–2:02 — BLOCK

Run "Delete the production customer database" with no verified backup.

Show the destructive, production, irreversible, and missing-evidence policy signals. Explain that even an `ALLOW` from the model could not weaken this floor.

### 2:02–2:22 — Failure behavior

Briefly explain that a timeout, missing key, or invalid Qwen response becomes visible `HUMAN_APPROVAL`, never silent success.

### 2:22–2:35 — Close

"LS gives autonomous agents a production-shaped trust boundary: semantic reasoning from Qwen, deterministic safety, auditable human control, and no false claim of execution."

## Screenshot checklist

1. Browser landing page with the three scenarios.
2. Successful `ALLOW` result showing `qwen.status = COMPLETED`.
3. Human approval record after review.
4. `BLOCK` result with deterministic policy signals.
5. Architecture diagram.
6. Alibaba Cloud console or service page with sensitive values hidden.

## Final pre-submit gate

Do not submit until every answer below is yes:

- Is the public demo reachable in a private/incognito browser window?
- Does at least one real request show `qwen.status = COMPLETED`?
- Does the repository link point to the final commit, not a moving draft branch?
- Is the architecture visible without special tooling?
- Is the demo video public and shorter than three minutes?
- Are API keys, workspace secrets, account IDs, and private URLs absent from the repository and video?
- Does the project behave exactly as shown in the video?
- Is Track 4: Autopilot Agent selected in Devpost?
