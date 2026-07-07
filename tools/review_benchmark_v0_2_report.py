from __future__ import annotations

from typing import Any

from review_benchmark_v0_2_binding import validate_case, validate_run_binding
from review_benchmark_v0_2_common import (
    VERDICTS,
    BenchmarkV02Error,
    confidence,
    exact,
    sha256_json,
    strings,
    text,
)
from review_benchmark_v0_2_finding import validate_finding
from review_benchmark_v0_2_structure import validate_structured


def validate_report(report: dict[str, Any], case: dict[str, Any], binding: dict[str, Any]) -> None:
    validate_case(case)
    if case["status"] != "FROZEN":
        raise BenchmarkV02Error("reports cannot be accepted until case is FROZEN")
    validate_run_binding(binding, case)
    exact(
        report,
        {
            "schema_version", "case_id", "lane", "evidence_sha256",
            "prompt_sha256", "run_binding_sha256", "verdict", "findings",
            "structured_analysis", "proposed_edges", "limitations",
        },
        "report",
    )
    if report["schema_version"] != "ls.review_benchmark_report.v0.2":
        raise BenchmarkV02Error("unsupported report schema_version")
    if report["case_id"] != case["case_id"]:
        raise BenchmarkV02Error("report case_id does not match case")
    if report["lane"] != binding["lane"]:
        raise BenchmarkV02Error("report lane does not match external run binding")
    if report["evidence_sha256"] != case["evidence_sha256"]:
        raise BenchmarkV02Error("report is not bound to frozen evidence")
    if report["prompt_sha256"] != binding["prompt_sha256"]:
        raise BenchmarkV02Error("report prompt digest does not match run binding")
    if report["run_binding_sha256"] != sha256_json(binding):
        raise BenchmarkV02Error("report run binding digest does not match binding")
    if report["verdict"] not in VERDICTS:
        raise BenchmarkV02Error("invalid report verdict")
    if not isinstance(report["findings"], list):
        raise BenchmarkV02Error("findings must be an array")

    finding_ids: set[str] = set()
    for index, item in enumerate(report["findings"]):
        validate_finding(item, index, finding_ids, report["lane"])
    validate_structured(report["structured_analysis"], report["lane"], finding_ids)

    if not isinstance(report["proposed_edges"], list):
        raise BenchmarkV02Error("proposed_edges must be an array")
    proposal_ids: set[str] = set()
    for index, edge in enumerate(report["proposed_edges"]):
        exact(
            edge,
            {"proposal_id", "source_node", "target_node", "relation_type", "provenance_finding_ids", "confidence", "status"},
            f"proposed_edges[{index}]",
        )
        proposal_id = text(edge["proposal_id"], "proposal_id")
        if proposal_id in proposal_ids:
            raise BenchmarkV02Error(f"duplicate proposal_id: {proposal_id}")
        proposal_ids.add(proposal_id)
        for name in ("source_node", "target_node", "relation_type"):
            text(edge[name], f"edge.{name}")
        refs = strings(edge["provenance_finding_ids"], "edge provenance", nonempty=True)
        if any(ref not in finding_ids for ref in refs):
            raise BenchmarkV02Error("edge references unknown finding provenance")
        confidence(edge["confidence"], "edge.confidence")
        if edge["status"] != "UNTRUSTED":
            raise BenchmarkV02Error("edge proposal must remain UNTRUSTED")
    strings(report["limitations"], "limitations")
