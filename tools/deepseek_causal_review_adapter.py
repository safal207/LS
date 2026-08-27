#!/usr/bin/env python3
"""Adapt one wrapper-owned DeepSeek causal lane into the LS review contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.causal_review import ContractError, validate_review

INPUT_SCHEMA_VERSION = "ls.deepseek-causal-lane.v0.1"
ROOT_KEYS = {
    "schema_version",
    "target",
    "model",
    "execution",
    "findings",
    "dedupe_overrides",
    "tests_to_run",
    "human_decision_points",
}
MODEL_KEYS = {"requested", "provider"}
EXECUTION_KEYS = {"status", "provenance", "details"}
FINDING_KEYS = {
    "source_id",
    "severity",
    "title",
    "location",
    "causal_chain",
    "evidence",
    "confidence",
    "reproduction",
    "recommendation",
}
SEVERITIES = {"info", "low", "medium", "high", "critical"}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
RISK_FROM_SEVERITY = {
    "info": "none",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


class DeepSeekAdapterError(ContractError):
    """Raised when DeepSeek provenance or native causal evidence is incomplete."""


def _object(
    value: Any,
    field: str,
    *,
    allowed: set[str] | None = None,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DeepSeekAdapterError(f"{field} must be an object")
    if allowed is not None:
        keys = set(value)
        extra = sorted(keys - allowed)
        missing = sorted(allowed - keys)
        if extra:
            raise DeepSeekAdapterError(
                f"{field} contains unknown properties: {', '.join(extra)}"
            )
        if missing:
            raise DeepSeekAdapterError(
                f"{field} is missing required properties: {', '.join(missing)}"
            )
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise DeepSeekAdapterError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise DeepSeekAdapterError(f"{field} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise DeepSeekAdapterError(f"{field} must not be empty")
    return result


def _string_array(value: Any, field: str) -> list[str]:
    return [
        _string(item, f"{field}[{index}]")
        for index, item in enumerate(_array(value, field))
    ]


def _severity(value: Any, field: str) -> str:
    severity = _string(value, field)
    if severity not in SEVERITIES:
        raise DeepSeekAdapterError(
            f"{field} must be one of: {', '.join(sorted(SEVERITIES))}"
        )
    return severity


def _provider_local_key(finding: Mapping[str, Any]) -> str:
    source_id = _string(finding.get("source_id"), "finding.source_id")
    location = _object(finding.get("location"), "finding.location")
    chain = _object(finding.get("causal_chain"), "finding.causal_chain")
    material = "\n".join(
        [
            source_id,
            str(location.get("path", "")),
            str(location.get("line", "")),
            str(chain.get("root_cause", "")),
            str(chain.get("failure_mechanism", "")),
        ]
    )
    return "external.deepseek." + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _adapt_finding(
    raw: Mapping[str, Any],
    index: int,
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    finding = _object(raw, f"findings[{index}]", allowed=FINDING_KEYS)
    source_id = _string(finding["source_id"], f"findings[{index}].source_id")
    severity = _severity(finding["severity"], f"findings[{index}].severity")
    override = overrides.get(source_id)
    if override is None:
        dedupe_key = _provider_local_key(finding)
    else:
        dedupe_key = _string(override, f"dedupe_overrides.{source_id}")
        if dedupe_key.startswith("external."):
            raise DeepSeekAdapterError(
                f"dedupe_overrides.{source_id} must not use the reserved external. prefix"
            )

    adapted = copy.deepcopy(dict(finding))
    adapted.pop("source_id")
    adapted["id"] = "DEEPSEEK-" + hashlib.sha256(
        source_id.encode("utf-8")
    ).hexdigest()[:8].upper()
    adapted["severity"] = severity
    adapted["claim_status"] = "CANDIDATE"
    adapted["dedupe_key"] = dedupe_key
    return adapted


def adapt_deepseek_lane(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate DeepSeek provenance and preserve only native causal findings."""
    lane = _object(payload, "lane", allowed=ROOT_KEYS)
    if lane["schema_version"] != INPUT_SCHEMA_VERSION:
        raise DeepSeekAdapterError(
            f"schema_version must equal {INPUT_SCHEMA_VERSION}"
        )

    target = dict(_object(lane["target"], "target"))
    model = _object(lane["model"], "model", allowed=MODEL_KEYS)
    requested_model = _string(model["requested"], "model.requested")
    provider_model_raw = model["provider"]
    provider_model = (
        None
        if provider_model_raw is None
        else _string(provider_model_raw, "model.provider")
    )
    execution = _object(
        lane["execution"], "execution", allowed=EXECUTION_KEYS
    )
    status = _string(execution["status"], "execution.status")
    provenance = _string(execution["provenance"], "execution.provenance")
    details = _string(
        execution["details"], "execution.details", allow_empty=True
    )
    raw_findings = _array(lane["findings"], "findings")
    overrides = _object(lane["dedupe_overrides"], "dedupe_overrides")
    tests_to_run = _string_array(lane["tests_to_run"], "tests_to_run")
    decisions = _string_array(
        lane["human_decision_points"], "human_decision_points"
    )

    if status != "COMPLETED":
        if raw_findings:
            raise DeepSeekAdapterError(
                f"{status} DeepSeek lane must not contain findings"
            )
        if overrides:
            raise DeepSeekAdapterError(
                f"{status} DeepSeek lane must not contain dedupe overrides"
            )
        return validate_review(
            {
                "schema_version": "ls.causal-review.v0.1",
                "reviewer": {
                    "id": "deepseek",
                    "display_name": "DeepSeek",
                    "model": provider_model or requested_model,
                },
                "target": target,
                "execution": {
                    "status": status,
                    "provenance": provenance,
                    "details": details,
                },
                "verdict": None,
                "risk_level": "none",
                "findings": [],
                "tests_to_run": [],
                "human_decision_points": [],
            }
        )

    if provenance != "MATCHED":
        raise DeepSeekAdapterError(
            "COMPLETED DeepSeek lane requires provenance=MATCHED"
        )
    if provider_model is None:
        raise DeepSeekAdapterError(
            "COMPLETED DeepSeek lane requires provider model identity"
        )
    if provider_model != requested_model:
        raise DeepSeekAdapterError(
            f"DeepSeek model mismatch: requested {requested_model}, provider returned {provider_model}"
        )

    source_ids = [
        _string(
            _object(raw, f"findings[{index}]").get("source_id"),
            f"findings[{index}].source_id",
        )
        for index, raw in enumerate(raw_findings)
    ]
    if len(source_ids) != len(set(source_ids)):
        raise DeepSeekAdapterError("DeepSeek finding source_id values must be unique")
    unknown_overrides = sorted(set(overrides) - set(source_ids))
    if unknown_overrides:
        raise DeepSeekAdapterError(
            "dedupe_overrides contains unknown source ids: "
            + ", ".join(unknown_overrides)
        )

    findings = [
        _adapt_finding(_object(raw, f"findings[{index}]"), index, overrides)
        for index, raw in enumerate(raw_findings)
    ]
    max_severity = max(
        (finding["severity"] for finding in findings),
        key=lambda value: SEVERITY_ORDER[value],
        default="info",
    )
    decisions = [
        "DeepSeek findings remain CANDIDATE and advisory; model agreement does not replace human adjudication.",
        *decisions,
    ]
    return validate_review(
        {
            "schema_version": "ls.causal-review.v0.1",
            "reviewer": {
                "id": "deepseek",
                "display_name": "DeepSeek",
                "model": provider_model,
            },
            "target": target,
            "execution": {
                "status": "COMPLETED",
                "provenance": "MATCHED",
                "details": details,
            },
            "verdict": "COMMENT",
            "risk_level": RISK_FROM_SEVERITY[max_severity],
            "findings": findings,
            "tests_to_run": tests_to_run,
            "human_decision_points": decisions,
        }
    )


def _read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise DeepSeekAdapterError(f"{path} must contain one JSON object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        review = adapt_deepseek_lane(_read_json(args.input))
        Path(args.output).write_text(
            json.dumps(review, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (DeepSeekAdapterError, ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"deepseek causal-review adapter error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
