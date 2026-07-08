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
DEFAULT_PR_NUMBER = "824"
DEFAULT_COMMIT_SHA = "f1cfdfbf5f648bc28434fb2f5a0cb77eb7e86666"
DEFAULT_CASE_ID = "pr824-ls-audit-v0.1"

EVIDENCE_PATHS = [
    "tools/validate_durable_approval_v0_1.py",
    "tools/test_durable_approval_schema_parity.py",
    "tools/validate_durable_approval_v0_2.py",
    "fixtures/trusted-runtime/durable-approval/event.schema.json",
]

EXPECTED_SCHEMA = {
    "schema_version": "ls.manual_real_model_audit_report.v0.1",
    "case_id": DEFAULT_CASE_ID,
    "model_attestation": {
        "provider": "LS",
        "model": "LS deterministic",
        "channel": "LS_RUN",
        "operator_note": "Independent LS audit of merged PR #824.",
    },
    "verdict": "APPROVE | REQUEST_CHANGES | INCOMPLETE",
    "findings": [],
    "limitations": [],
}

VALID_VERDICTS = {"APPROVE", "REQUEST_CHANGES", "INCOMPLETE"}
REQUIRED_REPORT_FIELDS = {
    "schema_version",
    "case_id",
    "model_attestation",
    "verdict",
    "findings",
    "limitations",
}


def read_text(path: str) -> str:
    file_path = ROOT / path
    if not file_path.is_file():
        raise FileNotFoundError(f"missing evidence file: {path}")
    return file_path.read_text(encoding="utf-8")


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_prompt(pr_number: str, commit_sha: str, case_id: str) -> str:
    evidence_lines = "\n".join(f"- {path}" for path in EVIDENCE_PATHS)
    expected_schema = json.dumps(
        {
            **EXPECTED_SCHEMA,
            "case_id": case_id,
        },
        indent=2,
        sort_keys=True,
    )
    return f"""Perform an independent LS audit of merged PR #{pr_number}.

Target:
https://github.com/safal207/LS/pull/{pr_number}

Merged commit:
{commit_sha}

Audit goal:
Check whether PR #{pr_number} correctly closes the durable approval schema/runtime parity gap for optional event fields without introducing new blocking defects.

Evidence scope:
{evidence_lines}

Return only JSON matching this shape:

{expected_schema}
"""


def build_evidence_pack(pr_number: str, commit_sha: str, case_id: str) -> dict[str, Any]:
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
        "pull_request": int(pr_number),
        "commit_sha": commit_sha,
        "audit_goal": "durable approval optional event field schema/runtime parity",
        "evidence_files": files,
        "prompt": build_prompt(pr_number, commit_sha, case_id),
        "expected_report_schema": {
            **EXPECTED_SCHEMA,
            "case_id": case_id,
        },
    }


def validate_ls_response(report: dict[str, Any], expected_case_id: str) -> list[str]:
    errors: list[str] = []

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
        if attestation.get("provider") != "LS":
            errors.append("model_attestation.provider must be LS")
        if not attestation.get("model"):
            errors.append("model_attestation.model is required")
        if not attestation.get("channel"):
            errors.append("model_attestation.channel is required")

    return errors


def build_scorecard(report: dict[str, Any] | None, errors: list[str]) -> dict[str, Any]:
    if report is None:
        ls_status: dict[str, Any] = {
            "status": "PENDING",
            "reason": "No LS response JSON was provided.",
        }
    elif errors:
        ls_status = {
            "status": "INVALID_REPORT",
            "errors": errors,
        }
    else:
        ls_status = {
            "status": "VALID_REPORT",
            "verdict": report["verdict"],
            "findings_count": len(report["findings"]),
        }

    return {
        "schema_version": "ls.audit_comparison_scorecard.v0.1",
        "case_id": DEFAULT_CASE_ID,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", default=DEFAULT_PR_NUMBER)
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
    out_dir = ROOT / args.out_dir
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

    report: dict[str, Any] | None = None
    errors: list[str] = []
    if args.ls_response_json:
        response_path = Path(args.ls_response_json)
        if not response_path.is_absolute():
            response_path = ROOT / response_path
        report = json.loads(response_path.read_text(encoding="utf-8"))
        errors = validate_ls_response(report, args.case_id)
        (out_dir / "ls_response_validation.json").write_text(
            json.dumps({"valid": not errors, "errors": errors}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    scorecard = build_scorecard(report, errors)
    scorecard["case_id"] = args.case_id
    (out_dir / "comparison_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Wrote LS audit artifacts to {out_dir.relative_to(ROOT)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
