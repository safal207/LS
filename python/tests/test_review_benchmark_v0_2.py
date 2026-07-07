from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
TESTS = Path(__file__).resolve().parent
for item in (TOOLS, TESTS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from review_benchmark_v0_2_binding import validate_run_binding  # noqa: E402
from review_benchmark_v0_2_common import BenchmarkV02Error, load_json  # noqa: E402
from review_benchmark_v0_2_report import validate_report  # noqa: E402
from review_benchmark_v0_2_seal import seal_report, validate_seal  # noqa: E402
from review_benchmark_v0_2_fixtures import binding_value, case_value, finding, report_value  # noqa: E402


class ReviewBenchmarkV02ContractTests(unittest.TestCase):
    def setUp(self):
        self.case = case_value()
        self.frontier_binding = binding_value()
        self.ls_binding = binding_value("LS")

    def validate(self, report, binding):
        validate_report(report, self.case, binding, ROOT)

    def test_user_attested_frontier_report_seals(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        seal = seal_report(self.case, self.frontier_binding, report, ROOT)
        self.assertEqual(seal["executor"]["model"], "Grok 4.5")
        self.assertEqual(seal["provenance_level"], "USER_ATTESTED")
        validate_seal(seal, report, self.frontier_binding)

    def test_model_cannot_self_declare_reviewer_identity(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        report["reviewer"] = {"system": "other", "model": "other", "version": "1"}
        with self.assertRaisesRegex(BenchmarkV02Error, "extra=.*reviewer"):
            self.validate(report, self.frontier_binding)

    def test_report_rejects_wrong_binding_digest(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        report["run_binding_sha256"] = "0" * 64
        with self.assertRaisesRegex(BenchmarkV02Error, "binding digest"):
            self.validate(report, self.frontier_binding)

    def test_report_rejects_lane_impersonation(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        report["lane"] = "LS"
        with self.assertRaisesRegex(BenchmarkV02Error, "external run binding"):
            self.validate(report, self.frontier_binding)

    def test_binding_mutation_invalidates_report(self):
        report = report_value("FRONTIER_MODEL", self.frontier_binding)
        changed = copy.deepcopy(self.frontier_binding)
        changed["executor"]["model"] = "different model"
        with self.assertRaisesRegex(BenchmarkV02Error, "binding digest"):
            self.validate(report, changed)

    def test_binding_prompt_digest_must_match_case(self):
        changed = copy.deepcopy(self.frontier_binding)
        changed["prompt_sha256"] = "0" * 64
        with self.assertRaisesRegex(BenchmarkV02Error, "frozen prompt"):
            validate_run_binding(changed, self.case, ROOT)

    def test_case_prompt_digest_must_match_prompt_bytes(self):
        changed = copy.deepcopy(self.case)
        changed["prompt_sha256"] = "0" * 64
        with self.assertRaisesRegex(BenchmarkV02Error, "prompt bytes"):
            validate_run_binding(self.frontier_binding, changed, ROOT)

    def test_api_and_workflow_provenance_require_matching_channels(self):
        for level, channel in (("API_VERIFIED", "API"), ("WORKFLOW_VERIFIED", "WORKFLOW")):
            binding = binding_value()
            binding["provenance"]["level"] = level
            with self.assertRaisesRegex(BenchmarkV02Error, f"requires {channel}"):
                validate_run_binding(binding, self.case, ROOT)

    def test_whitespace_only_text_is_rejected(self):
        item = finding("FRONTIER_MODEL")
        item["title"] = "   "
        report = report_value("FRONTIER_MODEL", self.frontier_binding, [item])
        with self.assertRaisesRegex(BenchmarkV02Error, "non-empty string"):
            self.validate(report, self.frontier_binding)

    def test_load_json_wraps_unicode_decode_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_bytes(b"\xff")
            with self.assertRaisesRegex(BenchmarkV02Error, "cannot load JSON"):
                load_json(path)

    def test_schema_files_are_valid_json_and_v02(self):
        for name in ("case-v0.2.schema.json", "run-binding-v0.2.schema.json", "report-v0.2.schema.json", "adjudication-v0.2.schema.json"):
            value = json.loads((ROOT / "benchmarks/review-comparison" / name).read_text(encoding="utf-8"))
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
