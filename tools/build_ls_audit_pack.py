#!/usr/bin/env python3
"""Build and validate an LS audit evidence package.

This helper intentionally does not call an external LS service. It makes the
human/model handoff deterministic by:

1. collecting the exact repository evidence files,
2. emitting the prompt and expected JSON report contract for LS,
3. optionally validating a saved LS JSON response against that contract, and
4. writing a compact comparison scorecard scaffold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PR_NUMBER = 824
DEFAULT_COMMIT_SHA = "f1cfdfbf5f648bc28434fb2f5a0cb77eb7e86666"
DEFAULT_CASE_ID = "pr824-ls-audit-v0.1"

EVIDENCE_PATHS = [
    "tools/validate_durable_approval_v0_1.py",
    "tools/test_durable_approval_schema_parity.py",
    "tools/validate_durable_approval_v0_2.py",
    "fixtures/trusted-runtime/durable-approval/event.schema.json",
]

VALID_VERDICTS = {"APPROVE", "REQUEST_CHANGES", "INCOMPLETE"}
EXPECTED_SCHEMA = {
    "schema_version": "ls.manual_real_model_audit_report.v0.1",
    "case_id": DEFAULT_CASE_ID,
    "model_attestation": {
        "provider": "LS",
        "model": "LS deterministic",
        "channel": "LS_RUN",
        "operator_note": "Independent LS audit of merged PR #824.",
    },
    "verdict": "APPROVE",
    "findings": [],
    "limitations": [],
}
REQUIRED_REPORT_FIELDS = {
    "schema_version",
    "case_id",
    "model_attestation",
    "verdict",
    "findings",
    "limitations",
}


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def read_text(path: str) -> str:
    file_path = ROOT / path
    if not file_path.is_file():
        raise FileNotFoundError(f"missing evidence file: {path}")
    return file_path.read_text(encoding="utf-8")


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_expected_report_schema(case_id: str) -> dict[str, Any]:
    return {
        **EXPECTED_SCHEMA,
        "case_id": case_id,
        "verdict_allowed_values": sorted(VALID_VERDICTS),
    }


def build_prompt(pr_number: int, commit_sha: str, case_id: str) -> str:
    evidence_lines = "\n".join(f"- {path}" for path in EVIDENCE_PATHS)
    expected_schema = json.dumps(
        build_expected_report_schema(case_id),
        indent=2,
        sort_keys=True,
    )
    allowed_verdicts = ", ".join(sorted(VALID_VERDICTS))
    return f"""Perform an independent LS audit of merged PR #{pr_number}.

Target:
https://github.com/safal207/LS/pull/{pr_number}

Merged commit:
{commit_sha}

Audit goal:
Check whether PR #{pr_number} correctly closes the durable approval schema/runtime parity gap for optional event fields without introducing new blocking defects.

Evidence scope:
{evidence_lines}

Return only JSON matching this shape. The verdict value must be exactly one of: {allowed_verdicts}.

{expected_schema}
"""


def build_evidence_pack(pr_number: int, commit_sha: str, case_id: str) -> dict[str, Any]:
    files = []
    for path in EVIDENCE_PATHS:
        content = read_text(path)
        files.append(
            {
                "path": path,
                "sha256": sha256_text(content),
                "line_count": len(content.splitlines()),
                "content": content,
            }
        )

    return {
        "schema_version": "ls.audit_evidence_pack.v0.1",
        "case_id": case_id,
        "repository": "safal207/LS",
        "pull_request": pr_number,
        "commit_sha": commit_sha,
        "audit_goal": "durable approval optional event field schema/runtime parity",
        "evidence_files": files,
        "prompt": build_prompt(pr_number, commit_sha, case_id),
        "expected_report_schema": build_expected_report_schema(case_id),
    }


def validate_ls_response(report: Any, expected_case_id: str) -> list[str]:
    errors: list[str] = []

    if not isinstance(report, dict):
        return ["report must be an object"]

    missing = REQUIRED_REPORT_FIELDS - report.keys()
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")

    if report.get("schema_version") != EXPECTED_SCHEMA["schema_version"]:
        errors.append("schema_version must be ls.manual_real_model_audit_report.v0.1")

    if report.get("case_id") != expected_case_id:
        errors.append(f"case_id must be {expected_case_id!r}")

    verdict = report.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append(f"verdict must be one of {sorted(VALID_VERDICTS)}")

    if not isinstance(report.get("findings"), list):
        errors.append("findings must be a list")

    if not isinstance(report.get("limitations"), list):
        errors.append("limitations must be a list")

    attestation = report.get("model_attestation")
    if not isinstance(attestation, dict):
        errors.append("model_attestation must be an object")
    else:
        for field in ("provider", "model", "channel", "operator_note"):
            if not isinstance(attestation.get(field), str) or not attestation.get(field):
                errors.append(f"model_attestation.{field} must be a non-empty string")
        if attestation.get("provider") != "LS":
            errors.append("model_attestation.provider must be LS")

    return errors


def build_scorecard(
    case_id: str,
    report: Any,
    errors: list[str],
) -> dict[str, Any]:
    if errors:
        ls_status: dict[str, Any] = {
            "status": "INVALID_REPORT",
            "errors": errors,
        }
    elif report is None:
        ls_status = {
            "status": "PENDING",
            "reason": "No LS response JSON was provided.",
        }
    else:
        if not isinstance(report, dict):
            raise TypeError("valid LS report must be an object")
        ls_status = {
            "status": "VALID_REPORT",
            "verdict": report["verdict"],
            "findings_count": len(report["findings"]),
        }

    return {
        "schema_version": "ls.audit_comparison_scorecard.v0.1",
        "case_id": case_id,
        "known_independent_model_result": {
            "provider": "OpenAI",
            "model": "GPT-5.5 High / Thinking",
            "verdict": "APPROVE",
            "findings_count": 0,
        },
        "human_adjudication_baseline": {
            "blocking_defect_confirmed": False,
            "status": "No blocking defect confirmed from available evidence.",
        },
        "ls_result": ls_status,
    }


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", default=DEFAULT_PR_NUMBER, type=positive_int)
    parser.add_argument("--commit-sha", default=DEFAULT_COMMIT_SHA)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--out-dir", default="artifacts/ls-audit")
    parser.add_argument(
        "--ls-response-json",
        default=None,
        help="Optional path to a saved LS JSON response to validate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    evidence_pack = build_evidence_pack(args.pr_number, args.commit_sha, args.case_id)
    (out_dir / "ls_audit_prompt.md").write_text(evidence_pack["prompt"], encoding="utf-8")
    (out_dir / "ls_audit_evidence_pack.json").write_text(
        json.dumps(evidence_pack, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "ls_audit_expected_schema.json").write_text(
        json.dumps(evidence_pack["expected_report_schema"], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report: Any = None
    errors: list[str] = []
    if args.ls_response_json:
        response_path = Path(args.ls_response_json)
        if not response_path.is_absolute():
            response_path = ROOT / response_path
        try:
            report = json.loads(response_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors = [
                f"ls response JSON is invalid: {exc.msg} at line {exc.lineno} column {exc.colno}"
            ]
        else:
            errors = validate_ls_response(report, args.case_id)
        (out_dir / "ls_response_validation.json").write_text(
            json.dumps({"valid": not errors, "errors": errors}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    scorecard = build_scorecard(
        args.case_id,
        report,
        errors,
    )
    (out_dir / "comparison_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Wrote LS audit artifacts to {display_path(out_dir)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
