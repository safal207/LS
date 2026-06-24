#!/usr/bin/env python3
"""Export deterministic LS and RAMR-canonical interoperability results."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "operational-continuity"
RUNNER_PATH = ROOT / "tools" / "run_operational_continuity_fixtures.py"
MAP_PATH = FIXTURE_DIR / "ramr-interop-map.json"
SHARED_RESULT_PATH = ROOT / "artifacts" / "ramr-ls-duplicate-successful-outcome-result.json"
OUTPUT_PATH = ROOT / "artifacts" / "ramr-operational-continuity-interop-result.json"

FIXTURE_FILES = (
    "resume_no_duplicate_side_effect.json",
    "superseded_approval_rejected.json",
    "complete_chain_preferred_over_disconnected_facts.json",
    "workspace_drift_requires_revalidation.json",
)


def _load_evaluator() -> Callable[[dict[str, Any]], dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("ls_continuity_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load fixture runner: {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def build_envelope() -> dict[str, Any]:
    mapping = _load_json(MAP_PATH)
    shared_result = _load_json(SHARED_RESULT_PATH)
    evaluate = _load_evaluator()

    results: list[dict[str, Any]] = []
    for filename in FIXTURE_FILES:
        fixture = _load_json(FIXTURE_DIR / filename)
        results.append(evaluate(fixture))

    outcome_counts = Counter(result["outcome"] for result in results)
    passed = sum(bool(result["passed"]) for result in results)

    return {
        "profile": mapping["profile"],
        "ramr": mapping["ramr"],
        "shared_evidence_envelope": mapping["shared_evidence_envelope"],
        "shared_evidence_result": shared_result,
        "ls": {
            "fixture_profile": "ls-operational-continuity-v0.1",
            "fixtures_total": len(results),
            "fixtures_passed": passed,
            "pass_rate": passed / len(results) if results else 0.0,
            "outcomes": {
                outcome: outcome_counts.get(outcome, 0)
                for outcome in ("RESUME", "REVALIDATE", "REJECT", "ABSTAIN")
            },
            "results": results,
        },
        "mappings": mapping["mappings"],
        "normative_rules": mapping["normative_rules"],
    }


def main() -> int:
    envelope = build_envelope()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(envelope, indent=2, sort_keys=True))

    ls_passed = envelope["ls"]["fixtures_passed"] == envelope["ls"]["fixtures_total"]
    shared = envelope["shared_evidence_result"]
    shared_passed = (
        shared.get("canonical_source", {}).get("local_mirror_verified") is True
        and shared.get("cases_passed") == shared.get("cases_total")
    )
    return 0 if ls_passed and shared_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
