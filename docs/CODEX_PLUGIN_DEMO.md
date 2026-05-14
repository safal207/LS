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

## 4. Accept The Proposal After Review

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

## 5. Why This Matters

Most AI sessions disappear into chat history. LS turns useful sessions into reviewable development signals while preserving consent and anti-surveillance boundaries.

Short version:

> Agents propose. LS reviews. Humans approve. The garden grows only after consent.

## Related Files

- [`plugins/ls-personal-cognitive-garden/README.md`](../plugins/ls-personal-cognitive-garden/README.md)
- [`plugins/ls-personal-cognitive-garden/skills/ls-pcg-gateway/SKILL.md`](../plugins/ls-personal-cognitive-garden/skills/ls-pcg-gateway/SKILL.md)
- [`plugins/ls-personal-cognitive-garden/scripts/route_gateway.py`](../plugins/ls-personal-cognitive-garden/scripts/route_gateway.py)
- [`docs/LS_PERSONAL_COGNITIVE_GARDEN.md`](LS_PERSONAL_COGNITIVE_GARDEN.md)
- [`docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md`](PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md)
