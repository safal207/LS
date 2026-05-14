# Session Continuity MVP Implementation Plan

## Purpose

This plan turns the Session Continuity Repair Layer from documentation into a small deterministic runtime MVP.

The MVP should prove one narrow loop:

```text
agent draft
-> LS continuity check
-> rupture detected or not
-> repair / hold / continue decision
-> JSON event artifact
-> human-readable summary
```

## Product goal

The first implementation should make this real:

```text
Do not let an agent continue from missing context when the last shared point is unknown.
```

The MVP is intentionally deterministic and rule-based.

It should not depend on an LLM to decide whether continuity is broken.

## Core thesis

```text
Continuity before continuation.
Evidence before action.
Consent before memory.
Repair before judgment.
```

## Non-goals

This MVP does not attempt to:

- solve hallucination generally;
- infer true human intent;
- replace Claude, Codex, Cursor, or Copilot;
- build a full TTM DB / LTP trace system;
- implement production security or compliance controls;
- build a full user interface;
- score employees or expose private cognitive graphs.

## Target file tree

```text
ls/
  continuity/
    __init__.py
    types.py
    detector.py
    repair.py
    policy.py

scripts/
  run_session_continuity_demo.py
  render_continuity_audit_report.py

examples/
  session_continuity/
    missing_pr_context.json
    repair_before_continue.json
    safe_continuation_with_context.json
    memory_write_without_consent.json
    action_without_causal_parent.json

tests/
  test_session_continuity_detector.py
  test_session_continuity_schema.py
  test_session_continuity_demo.py
```

## Core data model

Use the existing schema as the public artifact contract:

- `schemas/session-continuity-event.v0.1.json`

Runtime types should map to these fields:

```text
schema_version
event_id
session_id
agent_id
agent_type
expected_session_type
actual_response_type
continuity_status
rupture_detected
rupture_type
last_shared_point
missing_context
inferred_story
hallucination_risk
repair_prompt
next_safe_action
governance_decision
evidence
created_at
```

## Minimal Python types

`ls/continuity/types.py` should define:

```python
from dataclasses import dataclass, field
from typing import Literal

ContinuityStatus = Literal["intact", "uncertain", "ruptured", "repaired"]
HallucinationRisk = Literal["none", "low", "medium", "high"]
GovernanceDecision = Literal[
    "continue",
    "validate_context",
    "repair_before_continue",
    "hold_until_context",
    "human_review",
]

@dataclass(frozen=True)
class ContinuityInput:
    prompt: str
    raw_output: str
    session_id: str = "session_default"
    agent_id: str = "agent_default"
    agent_type: str = "other"
    available_context: dict = field(default_factory=dict)

@dataclass(frozen=True)
class ContinuityEvent:
    schema_version: str
    event_id: str
    session_id: str
    agent_id: str
    agent_type: str
    expected_session_type: str
    actual_response_type: str
    continuity_status: ContinuityStatus
    rupture_detected: bool
    rupture_type: str
    last_shared_point: str
    missing_context: list[str]
    inferred_story: str
    hallucination_risk: HallucinationRisk
    repair_prompt: str
    next_safe_action: GovernanceDecision
    governance_decision: GovernanceDecision
    evidence: list[dict]
    created_at: str
```

## Rule-based detector v0.1

`ls/continuity/detector.py` should implement a deterministic function:

```python
def detect_continuity(input: ContinuityInput) -> ContinuityEvent:
    ...
```

### Rule 1 — missing PR context

Trigger when:

```text
prompt contains continuation language:
  continue, дальше, продолжай, next, from that PR, после PR, тот PR

and available_context lacks:
  pr_url, pr_number, diff, branch, changed_files
```

Return:

```text
continuity_status: ruptured
rupture_type: missing_pr_context
hallucination_risk: high
next_safe_action: hold_until_context
governance_decision: hold_until_context
```

Repair:

```text
I should not continue from an inferred PR state. Please attach the PR, provide the PR number, or restate the exact change set before I continue.
```

### Rule 2 — support vs solution mismatch

Trigger when:

```text
prompt contains emotional support markers:
  scared, afraid, anxious, panic, worried, maybe this is useless,
  страшно, паника, волнуюсь, может зря, тревожно

and raw_output starts with direct problem-solving:
  steps, plan, roadmap, implementation, do X/Y/Z
```

Return:

```text
continuity_status: ruptured
rupture_type: session_type_mismatch
hallucination_risk: medium
next_safe_action: repair_before_continue
governance_decision: repair_before_continue
```

Repair:

```text
I may have moved into problem-solving while you needed support. Do you want presence, analysis, or next steps right now?
```

### Rule 3 — memory write without consent

Trigger when:

```text
raw_output proposes durable memory/profile/growth update
and prompt does not contain explicit approval/review/consent
```

Return:

```text
continuity_status: uncertain
rupture_type: memory_write_without_consent
hallucination_risk: medium
next_safe_action: human_review
governance_decision: human_review
```

Repair:

```text
Before this becomes durable memory, I need explicit human review and consent.
```

### Rule 4 — action without causal parent

Trigger when:

```text
raw_output proposes external action:
  merge, send, delete, deploy, pay, transfer, email, update production

and available_context lacks:
  approval, causal_parent, evidence, reversibility
```

Return:

```text
continuity_status: ruptured
rupture_type: action_without_causal_parent
hallucination_risk: high
next_safe_action: human_review
governance_decision: human_review
```

Repair:

```text
Before this action can proceed, I need declared intent, source evidence, causal parent, reversibility status, and explicit approval.
```

### Default rule — safe or uncertain continuation

If no rupture is detected:

```text
continuity_status: intact
rupture_detected: false
rupture_type: none
hallucination_risk: low
next_safe_action: continue
governance_decision: continue
```

## Repair prompt module

`ls/continuity/repair.py` should expose stable prompts by rupture type:

```python
def repair_prompt_for(rupture_type: str) -> str:
    ...
```

This keeps the detector stable and makes prompts reusable by CLI, gateway, and reports.

## Policy module

`ls/continuity/policy.py` should map rupture/risk to decision:

```python
def decision_for(rupture_type: str, hallucination_risk: str) -> str:
    ...
```

Simple v0.1 mapping:

```text
missing_pr_context + high -> hold_until_context
session_type_mismatch + medium -> repair_before_continue
memory_write_without_consent + medium/high -> human_review
action_without_causal_parent + high -> human_review
none + low -> continue
```

## CLI demo

`scripts/run_session_continuity_demo.py` should run at least three scenarios:

```text
1. missing_pr_context -> hold_until_context
2. support_vs_solution_mismatch -> repair_before_continue
3. safe_continuation_with_context -> continue
```

Expected human-readable output:

```text
Scenario: Missing PR context
Continuity: ruptured
Rupture type: missing_pr_context
Risk: high
Decision: hold_until_context
Repair: I should not continue from an inferred PR state...
```

Optional flags:

```bash
python scripts/run_session_continuity_demo.py --json
python scripts/run_session_continuity_demo.py --write-jsonl data/session_continuity_events.jsonl
```

## Gateway integration

Existing path:

```text
prompt + raw_output
-> LS gateway
-> action safety
-> optional PCG proposal
```

Target path:

```text
prompt + raw_output
-> continuity check
-> if rupture: repair / hold / human review
-> else: action safety
-> optional PCG proposal
```

Add to `plugins/ls-personal-cognitive-garden/scripts/route_gateway.py`:

```text
--continuity
--emit-continuity-event
--continuity-jsonl <path>
```

Expected CLI behavior:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "continue from that PR" \
  --raw-output "I will update the files now" \
  --continuity
```

Expected output:

```text
Session continuity: ruptured
Rupture type: missing_pr_context
Decision: hold_until_context
Repair prompt: I should not continue from an inferred PR state...
```

## Audit report renderer

`scripts/render_continuity_audit_report.py` should turn JSONL events into Markdown.

Input:

```text
data/session_continuity_events.jsonl
```

Output:

```text
reports/session_continuity_audit.md
```

Report sections:

```text
# AI Co-work Continuity Audit Report

Reviewed events
Ruptures detected
Top rupture classes
High-risk continuation cases
Repair prompts
Recommended gateway fields
Next integration steps
```

## Tests

### Detector tests

`tests/test_session_continuity_detector.py`:

- missing PR context returns `hold_until_context`;
- support mismatch returns `repair_before_continue`;
- memory write without consent returns `human_review`;
- action without causal parent returns `human_review`;
- safe continuation returns `continue`.

### Schema tests

`tests/test_session_continuity_schema.py`:

- generated events validate against `schemas/session-continuity-event.v0.1.json`;
- fixture examples validate against the same schema.

### Demo tests

`tests/test_session_continuity_demo.py`:

- demo script exits with status 0;
- output contains expected rupture types and decisions.

## Definition of Done

The MVP is complete when these commands work:

```bash
python scripts/run_session_continuity_demo.py
```

Shows:

```text
missing PR context -> hold_until_context
support mismatch -> repair_before_continue
safe continuation -> continue
```

And:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "continue from that PR" \
  --raw-output "I will update the files now" \
  --continuity
```

Shows:

```text
Session continuity: ruptured
Rupture type: missing_pr_context
Decision: hold_until_context
Repair prompt: ...
```

And tests pass:

```bash
pytest tests/test_session_continuity_detector.py tests/test_session_continuity_schema.py
```

## Recommended PR sequence

### PR 1 — docs

```text
docs: add session continuity MVP implementation plan
```

Adds this plan.

### PR 2 — core module

```text
feat: add deterministic session continuity detector
```

Adds:

```text
ls/continuity/types.py
ls/continuity/detector.py
ls/continuity/repair.py
ls/continuity/policy.py
```

### PR 3 — demo and examples

```text
feat: add session continuity demo runner
```

Adds:

```text
scripts/run_session_continuity_demo.py
examples/session_continuity/safe_continuation_with_context.json
examples/session_continuity/memory_write_without_consent.json
examples/session_continuity/action_without_causal_parent.json
```

### PR 4 — gateway integration

```text
feat: add continuity checks to Codex gateway script
```

Adds:

```text
--continuity
--emit-continuity-event
--continuity-jsonl
```

### PR 5 — audit report renderer

```text
feat: add continuity audit report renderer
```

Adds:

```text
scripts/render_continuity_audit_report.py
reports/session_continuity_audit_example.md
```

### PR 6 — tests

```text
test: add session continuity detector and schema tests
```

Adds:

```text
tests/test_session_continuity_detector.py
tests/test_session_continuity_schema.py
tests/test_session_continuity_demo.py
```

## Commercial tie-in

This MVP directly supports:

- `docs/offers/AI_COWORK_CONTINUITY_AUDIT.md`
- `docs/outreach/AI_COWORK_CONTINUITY_OUTREACH_KIT.md`
- `docs/TARGET_AUDIENCE_AND_OUTREACH_MAP.md`

The commercial promise becomes demoable:

```text
We can find where AI co-work breaks and show the repair gate.
```

## Research tie-in

This MVP supports the research question:

```text
Can hallucinated continuation be detected before it becomes action, memory, or evaluation?
```

The first evidence class is small but concrete:

```text
missing context in
-> rupture event out
-> repair/hold decision
```

## Final priority

Build the smallest deterministic loop first:

```text
broken context in
-> repair/hold decision out
```

Then integrate into gateway.

Then produce audit reports.

Then evaluate repeated patterns across sessions.
