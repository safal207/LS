from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "multi_model_review"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from exact_head_acquisition import load_manifest  # noqa: E402


class Pr796FinalCalibrationManifestTests(unittest.TestCase):
    def test_final_manifest_matches_merged_pr_head(self) -> None:
        manifest = load_manifest(
            ROOT / "benchmarks/exact-head/pr796-final-calibration-v0.1.json"
        )
        expected = {
            ".github/workflows/durable-approval-fixtures.yml",
            "docs/product/approval-integrity-30-second-demo.md",
            "fixtures/trusted-runtime/durable-approval/CONFORMANCE.md",
            "fixtures/trusted-runtime/durable-approval/README.md",
            "fixtures/trusted-runtime/durable-approval/configured_policy_expiry_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/durable_state_loss_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/envelope.schema.json",
            "fixtures/trusted-runtime/durable-approval/event.schema.json",
            "fixtures/trusted-runtime/durable-approval/pending_approval_not_missing_authority_v0.1.json",
            "fixtures/trusted-runtime/durable-approval/reconcile_in_doubt_committed_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/reconcile_in_doubt_failed_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/verified_context_invalidation_v0.2.json",
            "spec/durable-approval-conformance-v0.1.md",
            "spec/durable-approval-conformance-v0.2.md",
            "tools/demo_approval_integrity.py",
            "tools/test_durable_approval_v0_1.py",
            "tools/test_durable_approval_v0_2.py",
            "tools/validate_durable_approval_v0_1.py",
            "tools/validate_durable_approval_v0_2.py",
        }
        self.assertEqual(manifest.repository, "safal207/LS")
        self.assertEqual(manifest.pr_number, 796)
        self.assertEqual(
            manifest.expected_base_sha,
            "66353d32cafe9a7e2e4b62ee98575859eca9f531",
        )
        self.assertEqual(
            manifest.expected_head_sha,
            "c482e19d829c39bdffa1352e8579c2362e7699c4",
        )
        self.assertEqual(manifest.expected_changed_file_count, 19)
        self.assertEqual(set(manifest.artifact_paths), expected)
        self.assertEqual(manifest.related_artifacts, ())
        self.assertEqual(manifest.selection_mode, "ALL_CHANGED")


if __name__ == "__main__":
    unittest.main()
