from __future__ import annotations

from typing import Any

from review_benchmark_v0_2_common import BenchmarkV02Error, sha256_json
from review_benchmark_v0_2_report import validate_report


def _body(report: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "ls.review_benchmark_seal.v0.2",
        "case_id": report["case_id"],
        "lane": report["lane"],
        "evidence_sha256": report["evidence_sha256"],
        "prompt_sha256": report["prompt_sha256"],
        "run_binding_sha256": report["run_binding_sha256"],
        "run_id": binding["run_id"],
        "executor": binding["executor"],
        "provenance_level": binding["provenance"]["level"],
        "report_sha256": sha256_json(report),
        "finding_count": len(report["findings"]),
        "finding_ids": sorted(item["finding_id"] for item in report["findings"]),
        "proposed_edge_count": len(report["proposed_edges"]),
        "proposed_edge_ids": sorted(item["proposal_id"] for item in report["proposed_edges"]),
    }


def seal_report(case: dict[str, Any], binding: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    validate_report(report, case, binding)
    body = _body(report, binding)
    return {**body, "seal_sha256": sha256_json(body)}


def validate_seal(seal: dict[str, Any], report: dict[str, Any], binding: dict[str, Any]) -> None:
    if report.get("run_binding_sha256") != sha256_json(binding):
        raise BenchmarkV02Error("seal run binding does not match report")
    body = _body(report, binding)
    expected = {**body, "seal_sha256": sha256_json(body)}
    if seal == expected:
        return
    if seal.get("report_sha256") != expected["report_sha256"]:
        raise BenchmarkV02Error("report changed after it was sealed")
    for field, value in expected.items():
        if seal.get(field) != value:
            raise BenchmarkV02Error(f"seal {field} does not match report or binding")
    raise BenchmarkV02Error("seal contains unexpected fields")
