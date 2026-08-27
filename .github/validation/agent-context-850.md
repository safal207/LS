# Agent context latest validation

This PR adds the first advisory `agent_context.latest.json` export.

## Scope

- Add `.ci_exchange/schemas/agent_context.schema.json`.
- Add `.ci_exchange/agent_context.latest.json`.
- Add `docs/AGENT_CONTEXT.md`.
- Record the current command-bus route summary and prior route observations.

## Code impact

This change only adds JSON and Markdown metadata.

## Evidence used

- #846: Internet CI / CI Node Mesh epic.
- #847: command PR smoke.
- #848: command-bus route update.
- #849: CI Node Mesh registry and route export.
- workflow run `29027359506`.

## Expected validation

Existing CI should pass because this PR adds static metadata only.

Future work can generate this file automatically from `.ci_exchange` exports and CI memory artifacts.
