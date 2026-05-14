# Codex Plugin Demo: Agent Draft to Personal Cognitive Garden Proposal

This is the short "aha" path for the LS Personal Cognitive Garden plugin.

The point is simple:

```text
Codex or another agent drafts an answer
-> LS reviews it through the local gateway
-> risky actions are held
-> developmental sessions can emit a Personal Cognitive Garden proposal
-> durable memory is still blocked until human review
```

The next extension is session continuity repair:

```text
Codex or Claude tries to continue
-> LS checks whether the last shared point is known
-> missing context or session mismatch becomes a continuity event
-> LS repairs or holds before the agent invents continuity
```

## 1. Start The Local Gateway

From the repository root:

```bash
python -m ls.agent_shell.cli web-gateway --host 127.0.0.1 --port 8787
```

Health check:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --health
```

Expected result:

```json
{
  "ok": true,
  "service": "ls-web-agent-gateway",
  "token_required": false
}
```

## 2. Route A Developmental Agent Draft

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy AI session for skill growth and human development." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden."
```

Expected summary:

```text
LS decision: allow
Reason: constraints_satisfied
Gateway mode: pass_through
PCG proposal: yes
PCG status: proposed
Session class: skill_building
Human review required: True
Durable state allowed: False
Skill delta:
  - ai_session_review
  - development_signal_extraction
  - governed_memory_practice
```

## 3. What This Proves

The plugin demonstrates the first product loop:

```text
agent draft
-> safety/action review
-> optional development signal
-> proposed garden update
-> human review required
```

It does **not** write durable personal state automatically.

The safe default is:

```text
status: proposed
requires_human_review: true
durable_state_allowed: false
external_action_allowed: false
sharing_scope: private
```

## 4. Session Continuity Repair Use Case

The same gateway should also support continuity repair for Codex / Claude co-work.

Example failure:

```text
User: continue from that PR
Agent: starts implementing without the PR or diff
```

LS should record a continuity event instead of allowing invented continuity:

```text
rupture_type: missing_pr_context
hallucination_risk: high
governance_decision: hold_until_context
repair_prompt: Please attach the PR, provide the PR number, or restate the exact change set before I continue.
```

Example files:

- [`schemas/session-continuity-event.v0.1.json`](../schemas/session-continuity-event.v0.1.json)
- [`examples/session_continuity/missing_pr_context.json`](../examples/session_continuity/missing_pr_context.json)
- [`examples/session_continuity/repair_before_continue.json`](../examples/session_continuity/repair_before_continue.json)

## 5. Accept The Proposal After Review

When the operator explicitly approves the proposal, run:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy AI session for skill growth and human development." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden." \
  --accept \
  --reviewer "operator" \
  --review-note "Accepted as a reusable Codex session practice."
```

Expected acceptance fields:

```text
personal_cognitive_garden_acceptance.accepted: true
accepted_node.status: accepted
accepted_node.requires_human_review: false
accepted_node.governance.durable_state_allowed: true
accepted_node.governance.external_action_allowed: false
```

## 6. Reject A Weak Proposal

When the operator decides a proposal is too vague or wrong, run:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy AI session for skill growth and human development." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden." \
  --reject \
  --reviewer "operator" \
  --review-note "Too vague to preserve as a durable garden node."
```

Expected rejection fields:

```text
personal_cognitive_garden_rejection.rejected: true
rejected_node.status: rejected
rejected_node.requires_human_review: false
rejected_node.governance.durable_state_allowed: false
rejected_node.governance.external_action_allowed: false
```

## 7. Review The PCG Inbox

List every local garden proposal, collapsed by `garden_update_id`:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox
```

Filter by status:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox --status proposed
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox --status accepted
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox --status rejected
```

Expected summary:

```text
PCG Inbox: 3 total, 1 proposed, 1 accepted, 1 rejected
- pcg_update_<id> [accepted]
  class: skill_building / growth_path
  claim: This AI session may contain a reusable development signal...
```

## 8. Why This Matters

Most AI sessions disappear into chat history. LS turns useful sessions into reviewable development signals while preserving consent and anti-surveillance boundaries.

Session continuity repair adds a second safety layer:

```text
useful sessions can compound
broken sessions must repair before they continue
```

Short version:

> Agents propose. LS reviews. Humans approve. Broken sessions repair before they become invented continuity.

## Related Files

- [`plugins/ls-personal-cognitive-garden/README.md`](../plugins/ls-personal-cognitive-garden/README.md)
- [`plugins/ls-personal-cognitive-garden/skills/ls-pcg-gateway/SKILL.md`](../plugins/ls-personal-cognitive-garden/skills/ls-pcg-gateway/SKILL.md)
- [`plugins/ls-personal-cognitive-garden/scripts/route_gateway.py`](../plugins/ls-personal-cognitive-garden/scripts/route_gateway.py)
- [`docs/LS_PERSONAL_COGNITIVE_GARDEN.md`](LS_PERSONAL_COGNITIVE_GARDEN.md)
- [`docs/SESSION_CONTINUITY_REPAIR_LAYER.md`](SESSION_CONTINUITY_REPAIR_LAYER.md)
- [`docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md`](PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md)
