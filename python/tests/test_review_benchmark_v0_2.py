from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from review_benchmark_v0_2_scoring import score  # noqa: E402
from review_benchmark_v0_2_common import BenchmarkV02Error  # noqa: E402
from review_benchmark_v0_2_binding import validate_run_binding  # noqa: E402
from review_benchmark_v0_2_report import validate_report  # noqa: E402
from review_benchmark_v0_2_seal import seal_report, validate_seal  # noqa: E402
from review_benchmark_v0_2_fixtures import (  # noqa: E402
    EVIDENCE, binding_value, case_value, finding, report_value,
)


class ReviewBenchmarkV02Tests(unittest.TestCase):
    def setUp(self):
        self.case = case_value()
        self.frontier_binding = binding_value()
        self.ls_binding = binding_value("LS")

    def test_user_attested_frontier_report_seals(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        seal = seal_report(self.case, self.frontier_binding, report)
        self.assertEqual(seal["executor"]["model"], "Grok 4.5")
        self.assertEqual(seal["provenance_level"], "USER_ATTESTED")
        validate_seal(seal, report, self.frontier_binding)

    def test_model_cannot_self_declare_reviewer_identity(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        report["reviewer"] = {
            "system": "Claude",
            "model": "Claude-3.5-Sonnet",
            "version": "20241022",
        }
        with self.assertRaisesRegex(BenchmarkV02Error, "extra=.*reviewer"):
            validate_report(report, self.case, self.frontier_binding)

    def test_report_rejects_wrong_binding_digest(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        report["run_binding_sha256"] = "0" * 64
        with self.assertRaisesRegex(BenchmarkV02Error, "binding digest"):
            validate_report(report, self.case, self.frontier_binding)

    def test_report_rejects_lane_impersonation(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        report["lane"] = "LS"
        with self.assertRaisesRegex(BenchmarkV02Error, "external run binding"):
            validate_report(report, self.case, self.frontier_binding)

    def test_binding_mutation_invalidates_report(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        changed = copy.deepcopy(self.frontier_binding)
        changed["executor"]["model"] = "Gemini 2.5 Pro"
        with self.assertRaisesRegex(BenchmarkV02Error, "binding digest"):
            validate_report(report, self.case, changed)

    def test_api_verified_requires_api_channel(self):
        binding = binding_value()
        binding["provenance"]["level"] = "API_VERIFIED"
        with self.assertRaisesRegex(BenchmarkV02Error, "requires API"):
            validate_run_binding(binding, self.case)

    def test_workflow_verified_requires_workflow_channel(self):
        binding = binding_value()
        binding["provenance"]["level"] = "WORKFLOW_VERIFIED"
        with self.assertRaisesRegex(BenchmarkV02Error, "requires WORKFLOW"):
            validate_run_binding(binding, self.case)

    def test_ls_requires_nonempty_structured_analysis(self):
        report = report_value("LS", self.ls_binding)
        report["structured_analysis"] = {
            "artifact_nodes": [], "relations": [], "probes": [],
        }
        with self.assertRaisesRegex(BenchmarkV02Error, "LS report requires"):
            validate_report(report, self.case, self.ls_binding)

    def test_lane_specific_finding_prefix_is_enforced(self):
        bad = finding("FRONTIER_MODEL")
        bad["finding_id"] = "CLAUDE-001"
        report = report_value("FRONTIER_MODEL", self.frontier_binding, [bad])
        with self.assertRaisesRegex(BenchmarkV02Error, "must start with FM-"):
            validate_report(report, self.case, self.frontier_binding)

    def test_seal_binds_executor_and_provenance(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        seal = seal_report(self.case, self.frontier_binding, report)
        changed = copy.deepcopy(self.frontier_binding)
        changed["provenance"]["issuer"] = "different_operator"
        with self.assertRaisesRegex(BenchmarkV02Error, "seal .* does not match"):
            validate_seal(seal, report, changed)

    def test_score_uses_frontier_categories_and_records_provenance(self):
        fm_report = report_value(
            "FRONTIER_MODEL", self.frontier_binding, [finding("FRONTIER_MODEL")]
        )
        ls_report = report_value("LS", self.ls_binding, [finding("LS")])
        reports = {"FRONTIER_MODEL": fm_report, "LS": ls_report}
        bindings = {
            "FRONTIER_MODEL": self.frontier_binding,
            "LS": self.ls_binding,
        }
        seals = {
            lane: seal_report(self.case, bindings[lane], reports[lane])
            for lane in reports
        }
        adjudication = {
            "schema_version": "ls.review_benchmark_adjudication.v0.2",
            "case_id": "case-v0.2",
            "evidence_sha256": EVIDENCE,
            "adjudicator": "human",
            "ground_truth_complete": False,
            "known_truth": [],
            "clusters": [
                {
                    "cluster_id": "C001",
                    "canonical_claim": "Frontier-only true claim",
                    "members": [{
                        "lane": "FRONTIER_MODEL",
                        "finding_id": "FM-001",
                        "attribution_correct": True,
                    }],
                    "decision": "TRUE_STATICALLY_PROVEN",
                    "adjudicated_severity": "high",
                    "rationale": "Frozen evidence proves it.",
                },
                {
                    "cluster_id": "C002",
                    "canonical_claim": "LS false positive",
                    "members": [{
                        "lane": "LS",
                        "finding_id": "LS-001",
                        "attribution_correct": False,
                    }],
                    "decision": "FALSE_POSITIVE",
                    "adjudicated_severity": "none",
                    "rationale": "Not supported.",
                },
            ],
            "edge_decisions": [],
        }
        result = score(self.case, bindings, reports, seals, adjudication)
        self.assertEqual(
            result["cluster_analysis"][0]["category"],
            "FRONTIER_MODEL_ONLY_TRUE",
        )
        self.assertEqual(
            result["lanes"]["FRONTIER_MODEL"]["provenance_level"],
            "USER_ATTESTED",
        )
        self.assertIsNone(result["lanes"]["FRONTIER_MODEL"]["recall"])

    def test_every_finding_still_requires_adjudication(self):
        fm_report = report_value(
            "FRONTIER_MODEL", self.frontier_binding, [finding("FRONTIER_MODEL")]
        )
        ls_report = report_value("LS", self.ls_binding)
        reports = {"FRONTIER_MODEL": fm_report, "LS": ls_report}
        bindings = {
            "FRONTIER_MODEL": self.frontier_binding,
            "LS": self.ls_binding,
        }
        seals = {
            lane: seal_report(self.case, bindings[lane], reports[lane])
            for lane in reports
        }
        adjudication = {
            "schema_version": "ls.review_benchmark_adjudication.v0.2",
            "case_id": "case-v0.2",
            "evidence_sha256": EVIDENCE,
            "adjudicator": "human",
            "ground_truth_complete": False,
            "known_truth": [],
            "clusters": [],
            "edge_decisions": [],
        }
        with self.assertRaisesRegex(BenchmarkV02Error, "every finding"):
            score(self.case, bindings, reports, seals, adjudication)

    def test_schema_files_are_valid_json_and_v02(self):
        for name in (
            "case-v0.2.schema.json",
            "run-binding-v0.2.schema.json",
            "report-v0.2.schema.json",
            "adjudication-v0.2.schema.json",
        ):
            value = json.loads(
                (ROOT / "benchmarks/review-comparison" / name).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                value["$schema"],
                "https://json-schema.org/draft/2020-12/schema",
            )


if __name__ == "__main__":
    unittest.main()
