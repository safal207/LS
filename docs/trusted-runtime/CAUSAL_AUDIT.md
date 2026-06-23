# Trusted Runtime causal audit and CML boundary

Status: **reference implementation for issue #594**

LS records how a cooperative workflow progressed. CML checks whether important
transitions have inspectable causal ancestry.

```text
Cognitive Trail
-> CML-compatible causal records
-> deterministic local structural audit or optional CML CLI
-> CausalAuditReport
-> authorization guard
-> CAUSAL_AUDIT trail event
-> reusable artifact findings
```

## Ownership boundary

LS owns:

- workflow continuity and event order;
- mapping LS events into provider-neutral causal records;
- deciding whether a finding blocks the next authorization step;
- storing the audit report in the Cognitive Trail and reusable artifact.

CML owns:

- causal-audit semantics and rule evolution;
- native JSONL validation;
- findings such as missing parent, unmarked gap, and ambiguous root;
- independent CLI and SDK behavior.

LS does not copy the CML engine, and CML does not become an LS workflow
planner.

## Record mapping

Each trail is mapped to a synthetic task root followed by one causal record per
LS event. The CML-compatible JSONL fields are:

```json
{
  "id": "event-route",
  "timestamp": 2,
  "actor": {"pid": 0, "uid": 0, "comm": "runtime:ls"},
  "action": "connect",
  "object": {
    "kind": "ls_trail_event",
    "event_type": "ROUTE_SELECTED",
    "task_id": "task-001",
    "trail_id": "trail-001",
    "evidence_refs": ["evidence-001"],
    "delegation_ref": "delegate-reviewer",
    "high_impact": false
  },
  "permitted_by": "delegation:delegate-reviewer",
  "parent_cause": "event-plan"
}
```

The adapter exports identifiers and ancestry metadata, not full prompts, model
outputs, credentials, or private task content.

## Deterministic local validator

`DeterministicCausalAuditAdapter` is a dependency-free structural reference for
fixtures, CI, and offline review. It detects:

| Code | Meaning | Authorization effect |
| --- | --- | --- |
| `CML-AUDIT-R1-MISSING_PARENT` | parent record does not exist | block |
| `CML-AUDIT-R2-GAP_NOT_MARKED` | root/gap is not explicit | block |
| `CML-AUDIT-R4-AMBIGUOUS_ROOT` | root label is a near miss | block in LS |
| `LS-CML-R0-DUPLICATE_RECORD` | record identifier is duplicated | block |
| `LS-CML-R5-BROKEN_LINEAGE` | ancestry contains a cycle | block |
| `LS-CML-R6-ORPHAN_HIGH_IMPACT_ACTION` | high-impact action reaches neither task root nor approval | block |

The local validator is not presented as the CML engine. It exists so fixtures
remain inspectable when the external package is not installed.

## Authorization guard

```python
report = causal_adapter.audit(trail)
require_valid_causal_ancestry(report)
```

`require_valid_causal_ancestry()` raises `CausalAuthorizationBlocked` whenever
a blocking finding exists. Evidence gating, ProofPath packaging, or execution
authorization must happen only after this guard succeeds.

Operational success does not override causal invalidity.

## Optional CML CLI adapter

The external integration is disabled by default:

```python
adapter = CMLCausalAuditAdapter(
    CMLConfig(enabled=True, timeout_seconds=3.0)
)
report = adapter.audit(trail)
```

The default subprocess shape is equivalent to:

```text
cml audit <temporary-causal-trace.jsonl> --format json
```

The temporary directory is removed after the command completes. The command is
executed without a shell. Timeout, missing command, non-zero exit, invalid JSON,
and malformed findings fail closed.

## Recursive workers

A recursive worker may delegate another worker, but every resulting action must
still reach:

1. the original task root; or
2. an explicit approval ancestor.

A nested worker cannot manufacture a new root or create an orphan high-impact
action.

Fixtures cover:

```text
python/tests/fixtures/trusted-runtime/causal/
├── valid_recursive.json
├── missing_parent.json
├── ambiguous_root.json
└── broken_lineage.json
```

## Cognitive Trail and artifact export

`causal_audit_event()` creates a `CAUSAL_AUDIT` event containing the full
inspectable report.

`attach_causal_audit()` extends a reusable artifact payload with:

- `causal_audit_refs`;
- non-OK `causal_findings`.

The original reusable-artifact fields remain backward compatible; the causal
fields are optional schema extensions.

## Validation

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_causal_audit.py
```
