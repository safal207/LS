from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
TESTS = Path(__file__).resolve().parent
for item in (TOOLS, TESTS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from review_benchmark_v0_2_common import BenchmarkV02Error  # noqa: E402
from review_benchmark_v0_2_report import validate_report  # noqa: E402
from review_benchmark_v0_2_scoring import score  # noqa: E402
from review_benchmark_v0_2_seal import seal_report, validate_seal  # noqa: E402
from review_benchmark_v0_2_fixtures import EVIDENCE, binding_value, case_value, finding, report_value  # noqa: E402


class ReviewBenchmarkV02HardeningTests(unittest.TestCase):
    def setUp(self):
        self.case = case_value()
        self.frontier_binding = binding_value()
        self.ls_binding = binding_value("LS")

    def validate(self, report, binding):
        validate_report(report, self.case, binding, ROOT)

    def seal(self, binding, report):
        return seal_report(self.case, binding, report, ROOT)

    def test_ls_requires_nonempty_structured_analysis(self):
        report = report_value("LS", self.ls_binding)
        report["structured_analysis"] = {"artifact_nodes": [], "relations": [], "probes": []}
        with self.assertRaisesRegex(BenchmarkV02Error, "LS report requires"):
            self.validate(report, self.ls_binding)

    def test_lane_specific_finding_prefix_is_enforced(self):
        item = finding("FRONTIER_MODEL")
        item["finding_id"] = "OTHER-001"
        report = report_value("FRONTIER_MODEL", self.frontier_binding, [item])
        with self.assertRaisesRegex(BenchmarkV02Error, "must start with FM-"):
            self.validate(report, self.frontier_binding)

    def test_proposed_edge_requires_declared_nodes(self):
        item = finding("FRONTIER_MODEL")
        report = report_value("FRONTIER_MODEL", self.frontier_binding, [item])
        report["proposed_edges"] = [{
            "proposal_id": "edge-1", "source_node": "missing-a", "target_node": "missing-b",
            "relation_type": "depends_on", "provenance_finding_ids": ["FM-001"],
            "confidence": 0.8, "status": "UNTRUSTED",
        }]
        with self.assertRaisesRegex(BenchmarkV02Error, "unknown node"):
            self.validate(report, self.frontier_binding)

    def test_proposed_edge_accepts_declared_nodes(self):
        item = finding("FRONTIER_MODEL")
        report = report_value("FRONTIER_MODEL", self.frontier_binding, [item])
        report["structured_analysis"]["artifact_nodes"] = [
            {"node_id": "a", "kind": "source", "path": "tools/a.py", "observation": "A."},
            {"node_id": "b", "kind": "target", "path": "tools/b.py", "observation": "B."},
        ]
        report["proposed_edges"] = [{
            "proposal_id": "edge-1", "source_node": "a", "target_node": "b",
            "relation_type": "depends_on", "provenance_finding_ids": ["FM-001"],
            "confidence": 0.8, "status": "UNTRUSTED",
        }]
        self.validate(report, self.frontier_binding)

    def test_proven_reproduction_requires_steps(self):
        item = finding("FRONTIER_MODEL")
        item["reproduction"]["steps"] = []
        report = report_value("FRONTIER_MODEL", self.frontier_binding, [item])
        with self.assertRaisesRegex(BenchmarkV02Error, "must be an array"):
            self.validate(report, self.frontier_binding)

    def test_seal_binds_executor_and_provenance(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        seal = self.seal(self.frontier_binding, report)
        changed = binding_value()
        changed["provenance"]["issuer"] = "different_operator"
        with self.assertRaisesRegex(BenchmarkV02Error, "seal .* does not match"):
            validate_seal(seal, report, changed)

    def _score_inputs(self, fm_findings, ls_findings, decision):
        fm_report = report_value("FRONTIER_MODEL", self.frontier_binding, fm_findings)
        ls_report = report_value("LS", self.ls_binding, ls_findings)
        reports = {"FRONTIER_MODEL": fm_report, "LS": ls_report}
        bindings = {"FRONTIER_MODEL": self.frontier_binding, "LS": self.ls_binding}
        seals = {lane: self.seal(bindings[lane], reports[lane]) for lane in reports}
        members = [{"lane": "FRONTIER_MODEL", "finding_id": "FM-001", "attribution_correct": True}]
        if ls_findings:
            members.append({"lane": "LS", "finding_id": "LS-001", "attribution_correct": True})
        adjudication = {
            "schema_version": "ls.review_benchmark_adjudication.v0.2", "case_id": "case-v0.2",
            "evidence_sha256": EVIDENCE, "adjudicator": "human", "ground_truth_complete": False,
            "known_truth": [], "clusters": [{
                "cluster_id": "C001", "canonical_claim": "Claim", "members": members,
                "decision": decision, "adjudicated_severity": "high" if decision.startswith("TRUE") else "none",
                "rationale": "Adjudicated.",
            }], "edge_decisions": [],
        }
        return bindings, reports, seals, adjudication

    def test_score_records_frontier_category_provenance_and_prompt(self):
        inputs = self._score_inputs([finding("FRONTIER_MODEL")], [], "TRUE_STATICALLY_PROVEN")
        result = score(self.case, *inputs, ROOT)
        self.assertEqual(result["cluster_analysis"][0]["category"], "FRONTIER_MODEL_ONLY_TRUE")
        self.assertEqual(result["lanes"]["FRONTIER_MODEL"]["provenance_level"], "USER_ATTESTED")
        self.assertEqual(result["prompt_sha256"], self.case["prompt_sha256"])
        self.assertIsNone(result["lanes"]["FRONTIER_MODEL"]["recall"])

    def test_duplicate_findings_are_counted(self):
        inputs = self._score_inputs([finding("FRONTIER_MODEL")], [], "DUPLICATE")
        result = score(self.case, *inputs, ROOT)
        stats = result["lanes"]["FRONTIER_MODEL"]
        self.assertEqual(stats["duplicate_findings"], 1)
        self.assertEqual(stats["total_findings"], 1)

    def test_every_finding_still_requires_adjudication(self):
        fm_report = report_value("FRONTIER_MODEL", self.frontier_binding, [finding("FRONTIER_MODEL")])
        ls_report = report_value("LS", self.ls_binding)
        reports = {"FRONTIER_MODEL": fm_report, "LS": ls_report}
        bindings = {"FRONTIER_MODEL": self.frontier_binding, "LS": self.ls_binding}
        seals = {lane: self.seal(bindings[lane], reports[lane]) for lane in reports}
        adjudication = {
            "schema_version": "ls.review_benchmark_adjudication.v0.2", "case_id": "case-v0.2",
            "evidence_sha256": EVIDENCE, "adjudicator": "human", "ground_truth_complete": False,
            "known_truth": [], "clusters": [], "edge_decisions": [],
        }
        with self.assertRaisesRegex(BenchmarkV02Error, "every finding"):
            score(self.case, bindings, reports, seals, adjudication, ROOT)


if __name__ == "__main__":
    unittest.main()
