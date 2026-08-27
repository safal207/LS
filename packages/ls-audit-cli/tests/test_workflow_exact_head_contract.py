import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXACT_SOURCE_EXPRESSION = (
    "${{ github.event_name == 'pull_request' && "
    "github.event.pull_request.head.sha || github.sha }}"
)


class WorkflowExactHeadContractTests(unittest.TestCase):
    def test_pr_workflows_checkout_and_assert_the_exact_source_sha(self) -> None:
        for relative in (
            Path(".github/workflows/ls-audit-cli.yml"),
            Path(".github/workflows/ci.yml"),
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(f"EXACT_SOURCE_SHA: {EXACT_SOURCE_EXPRESSION}", text)
            self.assertIn("ref: ${{ env.EXACT_SOURCE_SHA }}", text)
            self.assertIn("Verify checked-out source identity", text)
            self.assertIn('test "$(git rev-parse HEAD)" = "$EXACT_SOURCE_SHA"', text)

    def test_live_audit_binds_tool_source_sha_into_the_manifest(self) -> None:
        text = (ROOT / ".github/workflows/ls-audit-cli.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"LS_TOOL_SOURCE_SHA: {EXACT_SOURCE_EXPRESSION}", text)
        self.assertIn(
            "assert manifest['tool']['source_sha'] == os.environ['EXPECTED_HEAD']",
            text,
        )


if __name__ == "__main__":
    unittest.main()
