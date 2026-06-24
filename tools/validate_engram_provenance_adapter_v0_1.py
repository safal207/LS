#!/usr/bin/env python3
"""Public-source Engram -> LS provenance adapter v0.1 conformance runner."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "engram-provenance" / "public-v4.12.0.json"
OUTPUT = ROOT / "artifacts" / "engram-provenance-adapter-v0.1-result.json"
ADAPTER = "engram-ls-provenance-v0.1"
REPO = "Patdolitse/piia-engram"
COMMIT = "dbf0a3d582eab69a829d094fde379c87c71e1823"
ITEM_TYPES = {"lesson", "decision", "playbook"}
METHODS = {"human": "human", "test_signal": "test", "anchor": "anchor"}


def clean(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def iso(value: object) -> str | None:
    value = clean(value)
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value


def adapt(item: dict[str, Any], item_type: str) -> dict[str, Any]:
    if item_type not in ITEM_TYPES:
        raise ValueError(f"unsupported source item type: {item_type}")
    item_id = clean(item.get("id"))
    if item_id is None:
        raise ValueError("Engram item id is required")

    tier = clean(item.get("tier")) or "verified"
    tool = clean(item.get("source_tool"))
    provenance = item.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    agent = clean(provenance.get("source_agent"))
    raw_method = clean(provenance.get("confirmation_source"))
    method = METHODS.get(raw_method)
    validated_at = iso(provenance.get("last_validated_at"))
    warnings: list[str] = []

    has_marker = raw_method is not None
    actor = agent if has_marker else None
    complete = (
        tier == "verified"
        and method is not None
        and actor is not None
        and validated_at is not None
    )

    if raw_method is not None and method is None:
        warnings.append(f"unsupported_confirmation_source:{raw_method}")
    if has_marker and validated_at is None:
        warnings.append("invalid_or_missing_last_validated_at")
    if has_marker and actor is None:
        warnings.append("confirmation_actor_missing")
    if has_marker and tier != "verified":
        warnings.append("typed_confirmation_without_verified_tier")
    if tier == "verified" and not complete:
        warnings.append("verified_without_typed_confirmation")

    assertion_agent = None if has_marker else agent
    if assertion_agent:
        level = "agent"
    elif tool:
        level = "tool"
    else:
        level = "unknown"
        warnings.append("assertion_identity_unknown")

    return {
        "source_item_id": item_id,
        "source_item_type": item_type,
        "assertion": {"tool": tool, "agent": assertion_agent, "attribution_level": level},
        "confirmation": {
            "state": "confirmed" if complete else "asserted",
            "actor": actor,
            "method": method,
            "validated_at": validated_at,
        },
        "advisory_only": True,
        "execution_authorized": False,
        "warnings": warnings,
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("fixture must be a JSON object")
    return value


def validate(fixture: dict[str, Any]) -> dict[str, Any]:
    meta = fixture.get("_meta")
    if not isinstance(meta, dict):
        raise ValueError("_meta must be an object")
    expected_meta = {
        "adapter_version": ADAPTER,
        "source_repository": REPO,
        "source_commit": COMMIT,
        "independent_compatibility_layer": True,
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            raise ValueError(f"fixture {key} mismatch")

    results = []
    seen: set[str] = set()
    for case in fixture.get("cases", []):
        if not isinstance(case, dict):
            raise ValueError("case must be an object")
        name = clean(case.get("case"))
        item_type = clean(case.get("source_item_type"))
        item = case.get("engram_item")
        expected = case.get("expected")
        if not name or name in seen or not item_type:
            raise ValueError("case name/type missing or duplicated")
        if not isinstance(item, dict) or not isinstance(expected, dict):
            raise ValueError(f"{name}: item/expected must be objects")
        seen.add(name)

        observed = adapt(item, item_type)
        errors = []
        if observed != expected:
            errors.append("projection differs from expected")
        if observed["source_item_id"] != item.get("id"):
            errors.append("source item id changed")
        if observed["execution_authorized"] is not False:
            errors.append("memory authorized execution")
        provenance = item.get("provenance")
        provenance = provenance if isinstance(provenance, dict) else {}
        if provenance.get("confirmation_source") is not None:
            if observed["assertion"]["agent"] is not None:
                errors.append("validator misattributed as assertion agent")
        results.append(
            {"case": name, "passed": not errors, "errors": errors, "observed": observed}
        )

    required = {
        "staging_assertion",
        "human_promoted_cross_tool",
        "test_signal_confirmation",
        "anchor_promoted",
        "verified_without_typed_confirmation",
        "confirmation_missing_validation_time",
    }
    if seen != required:
        raise ValueError(f"required case mismatch: {sorted(required - seen)}")

    methods = sorted(
        {
            row["observed"]["confirmation"]["method"]
            for row in results
            if row["observed"]["confirmation"]["state"] == "confirmed"
        }
    )
    warnings = sorted(
        {warning for row in results for warning in row["observed"]["warnings"]}
    )
    report = {
        "adapter_version": ADAPTER,
        "source": {
            "repository": REPO,
            "version": meta.get("source_version"),
            "commit": COMMIT,
            "license": meta.get("source_license"),
        },
        "independent_compatibility_layer": True,
        "cases_total": len(results),
        "cases_passed": sum(row["passed"] for row in results),
        "confirmed_methods_covered": methods,
        "warnings_observed": warnings,
        "boundary": {
            "advisory_only": True,
            "execution_authorized": False,
            "upstream_endorsement_claimed": False,
        },
        "results": results,
    }
    report["passed"] = (
        report["cases_passed"] == report["cases_total"]
        and methods == ["anchor", "human", "test"]
        and "verified_without_typed_confirmation" in warnings
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = validate(load(args.fixture))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
