# Engram provenance adapter v0.1

Status: **implemented by LS as an independent compatibility layer**.

This adapter consumes the public per-item shape implemented by
[`Patdolitse/piia-engram`](https://github.com/Patdolitse/piia-engram) and projects
only the provenance needed for LS conformance checks. It does not copy private
records, does not modify Engram, and does not imply endorsement, adoption, or
co-maintenance by the Engram project.

## 1. Source pin

- Repository: `Patdolitse/piia-engram`
- Version frame: `4.12.0`
- Commit: `dbf0a3d582eab69a829d094fde379c87c71e1823`
- License: `AGPL-3.0-or-later`

Public implementation artifacts used:

- `docs/specs/provenance-freshness-contract-v1.md`
- `docs/cross-tool-guide.md`
- `src/piia_engram/knowledge_ops.py`
- `src/piia_engram/reports_review.py`
- `src/piia_engram/staging_review.py`

## 2. Source semantics

The adapter preserves the distinction implemented by Engram:

- top-level `source_tool` identifies the tool that wrote the knowledge item;
- `provenance.source_agent` identifies the producer **or the last validator**;
- when `provenance.confirmation_source` is present, `source_agent` is interpreted
  as the validator actor, not as the original assertion agent;
- `provenance.confirmation_source` uses `human`, `test_signal`, or `anchor`;
- `provenance.last_validated_at` records the latest validation time;
- `tier` distinguishes `staging` and `verified`;
- `confirm_knowledge()` stamps confirmation metadata but does not promote tier;
- `promote_knowledge()` promotes to `verified` and stamps human confirmation;
- `accept_onboard_candidate()` promotes to `verified` and stamps anchor
  confirmation.

The adapter intentionally does not map a post-confirmation `source_agent` to
`asserted_by`.

## 3. Normalized projection

```json
{
  "source_item_id": "lesson-codex-001",
  "source_item_type": "lesson",
  "assertion": {
    "tool": "codex",
    "agent": null,
    "attribution_level": "tool"
  },
  "confirmation": {
    "state": "confirmed",
    "actor": "owner",
    "method": "human",
    "validated_at": "2026-06-24T17:00:00Z"
  },
  "advisory_only": true,
  "execution_authorized": false,
  "warnings": []
}
```

`assertion.attribution_level` is:

- `agent` when an unconfirmed item retains a producer `source_agent`;
- `tool` when only `source_tool` can be preserved safely;
- `unknown` when neither source field is usable.

## 4. Confirmation rules

Confirmation method mapping:

| Engram | Adapter |
|---|---|
| `human` | `human` |
| `test_signal` | `test` |
| `anchor` | `anchor` |

The adapter emits `confirmation.state = "confirmed"` only when all of these
conditions hold:

1. `tier == "verified"`;
2. `confirmation_source` is recognized;
3. validator actor (`provenance.source_agent`) is present;
4. `last_validated_at` is parseable ISO-8601.

Otherwise the item remains `asserted` and receives a warning. This is
deliberately stricter than treating the `verified` tier alone as sufficient.

## 5. Warnings

The v0.1 warning vocabulary is:

- `unsupported_confirmation_source:<value>`
- `invalid_or_missing_last_validated_at`
- `confirmation_actor_missing`
- `typed_confirmation_without_verified_tier`
- `verified_without_typed_confirmation`
- `assertion_identity_unknown`

Warnings never authorize an action and never invent missing identities.

## 6. Boundary invariants

1. The Engram item `id` is preserved as the stable source binding.
2. A later validator cannot overwrite the original `source_tool` attribution.
3. A validator `source_agent` is not re-labeled as the original assertion agent.
4. Similarity, repeated retrieval, access count, or model agreement cannot create
   confirmation.
5. A verified item without typed confirmation metadata fails closed.
6. Missing model or version identity remains tool-level or unknown.
7. All memory remains advisory-only.
8. `execution_authorized` is always `false`.
9. The adapter makes no upstream endorsement claim.

## 7. Conformance vectors

The public fixture covers:

- staging assertion written by Codex;
- human promotion while preserving Codex as original tool;
- test-signal confirmation;
- anchor confirmation;
- legacy verified item without typed confirmation;
- incomplete confirmation missing validation time.

Run:

```bash
python tools/validate_engram_provenance_adapter_v0_1.py
```

The validator writes:

```text
artifacts/engram-provenance-adapter-v0.1-result.json
```

## 8. Upstream interaction

LS builds and maintains this adapter from public artifacts. An upstream Engram
issue or pull request is appropriate only when a specific reproducible
compatibility defect is found.
