# CI Exchange Metadata Validation

LS stores reusable CI route memory in `.ci_nodes` and `.ci_exchange`.

The metadata validator checks that this memory remains internally consistent.

## Validator

```bash
python tools/validate_ci_exchange.py
```

The validator checks:

- `.ci_nodes/registry.json` contains node entries;
- registry node manifests exist and match their node ids;
- route exports include a best path, markers, evidence, and applicability boundaries;
- context exports include claims and evidence;
- anti-pattern exports include symptom, impact, replacement, and evidence;
- `agent_context.latest.json` points only to existing generated sources;
- the current working Grok command PR route is still present in agent context.

## Tests

```bash
python -m pytest tools/test_ci_exchange_metadata.py
```

## Why this matters

The CI Node Mesh is only useful if its memory files remain coherent.

This validator makes the memory layer harder to accidentally break when adding or editing route exports, context packs, or node manifests.

## Boundary

This validator checks static metadata consistency. It does not run workflows, approve pull requests, or decide whether a route is operationally healthy today.
