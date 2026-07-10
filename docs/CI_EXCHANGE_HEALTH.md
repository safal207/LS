# CI Exchange Health Report

The CI Exchange health report is a compact human- and agent-readable summary of the metadata memory layer.

Generated files:

```text
.ci_exchange/health.latest.json
.ci_exchange/health.latest.md
```

## Generate

```bash
python tools/generate_ci_exchange_health.py
```

## Check committed reports

```bash
python tools/generate_ci_exchange_health.py --check
```

## What it reports

The health report summarizes these static checks:

- registry entries and node manifests;
- route exports;
- context exports;
- anti-pattern exports;
- latest agent context.

## Difference from the validator

`tools/validate_ci_exchange.py` is the guardrail: it returns errors when metadata is inconsistent.

`tools/generate_ci_exchange_health.py` is the status view: it turns validator output into a compact report that can be read by people, agents, or CI summaries.

## Boundary

The report covers static metadata health. It does not prove live provider availability or real-time route execution health.
