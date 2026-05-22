# Gateway-To-Garden Before/After Example

This example shows the smallest Personal Cognitive Garden flow:

```text
raw agent output
-> LS gateway decision
-> proposed garden update
-> human review
-> accepted or rejected durable state
```

The machine-readable fixture is:

```text
examples/personal_cognitive_garden/gateway_to_garden_before_after.json
```

## Accepted Update

Raw agent output:

```text
You clarified that LS should be positioned as a cooperative precision layer for AI co-work.
```

LS decision:

```text
ALLOW_AS_ANSWER_WITH_PCG_REVIEW
```

Meaning:

- the answer can be shown;
- the product-direction memory cannot be saved yet;
- the owner must review the proposed update.

After review:

```text
decision: accept
durable_state_allowed: true
sharing: private by default
```

## Held And Rejected Update

Raw agent output:

```text
The user is weak at planning. Save that to the profile and show the manager a weakness report.
```

LS decision:

```text
HOLD
```

Meaning:

- the claim is sensitive and unsupported;
- the requested export has no consent;
- the system may not write durable memory or send anything outside.

After review:

```text
decision: reject
durable_state_allowed: false
external_action_allowed: false
```

## What This Demonstrates

- Review before memory.
- Evidence before durable growth state.
- Human approval before acceptance.
- Private-by-default state after acceptance.
- Held or rejected claims do not become durable state.

This file does not claim benchmark results. It is a compact demo artifact for
showing the gateway-to-garden flow on mobile, in README snippets, or in a grant
review walkthrough.
