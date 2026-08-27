# CI Node Mesh registry validation

This PR introduces static CI Node Mesh and CI Exchange metadata.

## Scope

- Add initial `.ci_nodes/registry.json`.
- Add JSON schemas for CI node, command, memory event, context, route, and anti-pattern records.
- Export the validated Grok command-bus route.
- Export the connector-safe command-bus context.
- Document the current winning route in `docs/CI_NODE_MESH.md`.

## Runtime impact

No workflow runtime behavior is changed by this PR.

## Evidence recorded

- #846: Internet CI / CI Node Mesh epic.
- #847: validation-only command PR.
- #848: merged command-bus switch to `pull_request`.
- workflow run `29027359506`: successful command-bus smoke.

## Validation expectation

Existing CI should pass because this PR only adds static JSON/Markdown metadata.

Future PRs can add schema validation for `.ci_nodes` and `.ci_exchange`.
