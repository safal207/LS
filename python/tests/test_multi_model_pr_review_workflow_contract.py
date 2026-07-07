from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "multi_model_pr_review.yml"


class MultiModelPrReviewWorkflowContractTests(unittest.TestCase):
    def test_comment_publication_has_explicit_write_permissions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        permissions = text.split("permissions:", 1)[1].split("concurrency:", 1)[0]

        self.assertIn("contents: read", permissions)
        self.assertIn("issues: write", permissions)
        self.assertIn("pull-requests: write", permissions)
        self.assertNotIn("pull-requests: read", permissions)

    def test_publication_remains_exact_head_guarded(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        guard_index = text.index("Re-check exact head before publication")
        publish_index = text.index("Publish or update the exact-head PR summary")

        self.assertLess(guard_index, publish_index)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", text)
        self.assertIn("persist-credentials: false", text)


if __name__ == "__main__":
    unittest.main()
