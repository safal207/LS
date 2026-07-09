# CI Exchange Health Report

Status: ✅ `pass`

CI Exchange metadata is internally consistent.

## Sections

| Section | Status | Count | Detail |
| --- | --- | ---: | --- |
| registry | ✅ `pass` | 3 | registered CI nodes |
| node_manifests | ✅ `pass` | 3 | reachable node manifests |
| routes | ✅ `pass` | 1 | route exports |
| contexts | ✅ `pass` | 1 | context exports |
| anti_patterns | ✅ `pass` | 1 | anti-pattern exports |
| agent_context | ✅ `pass` | 4 | known route entries |

## Validated paths

- `.ci_nodes/registry.json`
- `.ci_exchange/routes`
- `.ci_exchange/contexts`
- `.ci_exchange/anti_patterns`
- `.ci_exchange/agent_context.latest.json`

## Errors

No metadata validation errors were found.

## Authority boundary

Health reports describe static metadata consistency only; they do not approve, merge, deploy, or replace operational smoke tests.
