from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from validate_visual_benchmark import ValidationError, validate  # noqa: E402

TRAIL_FIXTURE = ROOT / "fixtures" / "robys_pr_164_wordmark.json"
AXIS_FIXTURE = ROOT / "fixtures" / "robys_pr_164_visual_benchmark_2026_07.json"


class VisualBenchmarkAxisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trail = json.loads(TRAIL_FIXTURE.read_text(encoding="utf-8"))
        self.axis = json.loads(AXIS_FIXTURE.read_text(encoding="utf-8"))

    def assert_invalid(self, axis: dict, message: str) -> None:
        with self.assertRaisesRegex(ValidationError, message):
            validate(self.trail, axis)

    def assessment(self, axis: dict, criterion_id: str) -> dict:
        return next(item for item in axis["assessments"] if item["criterionId"] == criterion_id)

    def pattern(self, axis: dict, pattern_id: str) -> dict:
        return next(item for item in axis["patternDecisions"] if item["patternId"] == pattern_id)

    def test_real_visual_benchmark_is_valid(self) -> None:
        validate(self.trail, self.axis)
        self.assertEqual(self.axis["benchmarkWindow"]["periodKey"], "2026-07")
        self.assertFalse(self.axis["summary"]["mergeAuthority"])

    def test_axis_must_bind_to_exact_trail_head(self) -> None:
        axis = copy.deepcopy(self.axis)
        axis["subject"]["head"] = self.trail["subject"]["baseHead"]
        self.assert_invalid(axis, "subject head must match")

    def test_period_key_must_match_observation_month(self) -> None:
        axis = copy.deepcopy(self.axis)
        axis["benchmarkWindow"]["periodKey"] = "2026-06"
        self.assert_invalid(axis, "periodKey must match")

    def test_stale_source_is_rejected(self) -> None:
        axis = copy.deepcopy(self.axis)
        axis["sources"][0]["validUntil"] = "2026-07-01T00:00:00Z"
        self.assert_invalid(axis, "already stale")

    def test_fast_moving_source_cannot_claim_long_validity(self) -> None:
        axis = copy.deepcopy(self.axis)
        source = next(item for item in axis["sources"] if item["class"] == "TREND_FEED")
        source["validUntil"] = "2027-07-01T00:00:00Z"
        self.assert_invalid(axis, "overlong validity window")

    def test_normative_criterion_requires_normative_source(self) -> None:
        axis = copy.deepcopy(self.axis)
        self.assessment(axis, "criterion.accessibility")["sourceIds"] = ["source.apple-hig"]
        self.assert_invalid(axis, "requires a NORMATIVE source")

    def test_gap_is_recomputed(self) -> None:
        axis = copy.deepcopy(self.axis)
        self.assessment(axis, "criterion.motion")["gap"] = 0.1
        self.assert_invalid(axis, "gap must equal")

    def test_trend_only_pattern_cannot_be_adopted(self) -> None:
        axis = copy.deepcopy(self.axis)
        pattern = self.pattern(axis, "pattern.tactile-editorial-texture")
        pattern["status"] = "ADOPT"
        pattern["sourceIds"] = ["source.awwwards-sotd-2026-07"]
        pattern["experimentGuard"] = None
        axis["summary"]["experimentalPatternIds"].remove(pattern["patternId"])
        axis["summary"]["adoptedPatternIds"].append(pattern["patternId"])
        self.assert_invalid(axis, "cannot be adopted from trend evidence alone")

    def test_experiment_requires_guard(self) -> None:
        axis = copy.deepcopy(self.axis)
        self.pattern(axis, "pattern.expressive-micro-motion")["experimentGuard"] = None
        self.assert_invalid(axis, "requires an experimentGuard")

    def test_summary_score_is_recomputed(self) -> None:
        axis = copy.deepcopy(self.axis)
        axis["summary"]["weightedCurrentScore"] = 4.99
        self.assert_invalid(axis, "weightedCurrentScore")

    def test_benchmark_never_grants_merge_authority(self) -> None:
        axis = copy.deepcopy(self.axis)
        axis["summary"]["mergeAuthority"] = True
        self.assert_invalid(axis, "must never grant merge authority")


if __name__ == "__main__":
    unittest.main()
