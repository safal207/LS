# CI Exchange Health Report

Status: **PASS**

## Checks

| Check | Status | Summary |
| --- | --- | --- |
| `registry` | `pass` | CI node registry is present and references reachable node manifests. |
| `routes` | `pass` | Route exports include best path, markers, evidence, and applicability boundaries. |
| `contexts` | `pass` | Context exports include summary, claims, and evidence. |
| `anti_patterns` | `pass` | Anti-pattern exports include symptom, impact, replacement, and evidence. |
| `agent_context` | `pass` | Latest agent context references existing sources and keeps key route memory. |

## Generated from

- `tools/validate_ci_exchange.py`
- `.ci_nodes/registry.json`
- `.ci_exchange/routes/grok-review-command-bus.route.json`
- `.ci_exchange/contexts/connector-safe-command-bus.context.json`
- `.ci_exchange/anti_patterns/connector-issue-comment-trigger.antipattern.json`
- `.ci_exchange/agent_context.latest.json`

## Boundary

This report checks static CI Exchange metadata health only. It does not run the Grok command bus, call external model providers, approve pull requests, or prove that a route is operationally healthy right now.
