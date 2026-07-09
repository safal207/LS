# CI Exchange Health Report

The CI Exchange health report summarizes the current state of LS metadata used by agent memory.

Generated files:

```text
.ci_exchange/health/ci_exchange_health.json
.ci_exchange/health/ci_exchange_health.md
```

Generator:

```bash
python tools/generate_ci_exchange_health.py
```

Check mode:

```bash
python tools/generate_ci_exchange_health.py --check
```

## What the report covers

The report summarizes:

- registry entries;
- reachable node manifests;
- route exports;
- context exports;
- anti-pattern exports;
- latest agent context entries;
- validation errors, if any.

## Boundary

The report describes static metadata consistency only. It does not prove that an external model, provider, or route is operational at the current moment.

Operational route checks should be added separately as smoke tests.
