# CI Exchange Health Report

Status: **PASS**

CI Exchange metadata is internally consistent.

## Checks

| Check | Status | Details |
| --- | --- | --- |
| metadata_validator | pass | error_count=0 |
| registry | pass | node_count=3, manifest_count=3 |
| routes | pass | route_count=1 |
| contexts | pass | context_count=1 |
| anti_patterns | pass | anti_pattern_count=1 |
| agent_context | pass | generated_from_count=4, known_working_route_count=1, known_bad_route_count=3 |

## Counts

- nodes: 3
- node_manifests: 3
- routes: 1
- contexts: 1
- anti_patterns: 1
- agent_context_sources: 4
- known_working_routes: 1
- known_bad_routes: 3

## Boundary

This report checks static CI Exchange metadata consistency. It does not prove that external services are currently available.
