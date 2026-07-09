# CI Exchange Health Report

The CI Exchange health report is a compact status snapshot for LS CI Node Mesh metadata.

It is generated from the same metadata that powers the agent context and the metadata validator.

## Files

```text
.ci_exchange/health/latest.json
.ci_exchange/health/latest.md
tools/generate_ci_exchange_health.py
tools/test_ci_exchange_health.py
```

## Generate

```bash
python tools/generate_ci_exchange_health.py
```

## Check

```bash
python tools/generate_ci_exchange_health.py --check
python -m pytest tools/test_ci_exchange_health.py
```

## What the report shows

The report summarizes:

- overall metadata status;
- validator error count;
- registry and manifest counts;
- route export count;
- context export count;
- anti-pattern count;
- latest agent context source and route counts.

## Boundary

This report checks static metadata health. It does not prove that external services are currently reachable or that a command route is operational at the moment of reading.

Operational route checks should be added separately as command-bus smoke or readiness reports.
