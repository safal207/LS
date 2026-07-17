import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cml_git_internet as cml
import ls_audit_cml_cli as integration

HEAD = "a" * 40
BASE = "b" * 40
PIN = "d" * 40


class TargetClient:
    def get(self, endpoint: str):
        if endpoint == "/repos/acme/app/pulls/7":
            return {
                "html_url": "https://github.com/acme/app/pull/7",
                "number": 7,
                "title": "Example",
                "state": "open",
                "draft": False,
                "user": {"login": "author"},
                "head": {"sha": HEAD, "ref": "feature"},
                "base": {"sha": BASE, "ref": "main"},
                "changed_files": 0,
                "additions": 0,
                "deletions": 0,
            }
        if endpoint == f"/repos/acme/app/commits/{HEAD}/status":
            return {"state": "success", "total_count": 0, "statuses": []}
        if endpoint == f"/repos/acme/app/commits/{HEAD}/check-runs?per_page=100":
            return {"total_count": 0, "check_runs": []}
        raise AssertionError(endpoint)

    def pages(self, endpoint: str):
        if endpoint in {
            "/repos/acme/app/pulls/7/files",
            "/repos/acme/app/pulls/7/reviews",
        }:
            return []
        raise AssertionError(endpoint)


class CompatibilityTests(unittest.TestCase):
    def test_no_registry_preserves_original_network_boundary_and_bundle_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "bundle"
            with mock.patch.object(
                integration.base, "ValidatedClient", return_value=TargetClient()
            ), mock.patch.object(
                integration,
                "anonymous_cml_client",
                side_effect=AssertionError("CML network must not run"),
            ):
                code = integration.main(
                    [
                        "https://github.com/acme/app/pull/7",
                        "--expected-head",
                        HEAD,
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 0)
            card = json.loads((output / "scorecard.json").read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertNotIn("causal_memory", card["lanes"])
            self.assertFalse((output / "evidence/cml-memory.json").exists())
            self.assertEqual(manifest["tool"]["version"], integration.TOOL_VERSION)

    def test_initial_exact_head_mismatch_blocks_cml_network(self) -> None:
        registry = cml.Registry((cml.Source("acme/cml", PIN),))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            evidence = output / "evidence"
            evidence.mkdir()
            (evidence / "pr.json").write_text(
                json.dumps(
                    {
                        "title": "stale target",
                        "head": {"sha": "c" * 40},
                        "base": {"sha": BASE},
                    }
                )
            )
            with mock.patch.object(
                integration,
                "anonymous_cml_client",
                side_effect=AssertionError("CML network must not run"),
            ):
                result, digest = integration.collect_cml(
                    registry=registry,
                    output=output,
                    ref=integration.core.Ref("github.com", "acme", "app", 7),
                    expected_head=HEAD,
                    timeout=1.0,
                )
            self.assertEqual(result["lane_status"], "NOT_RUN")
            self.assertEqual(
                result["sources"][0]["reason_code"],
                "INITIAL_EXACT_HEAD_MISMATCH",
            )
            self.assertEqual(len(digest), 64)
            self.assertFalse(any(result["authority"].values()))


class RenderingTests(unittest.TestCase):
    def test_public_memory_cannot_inject_scorecard_markdown_or_html(self) -> None:
        section = integration.render_cml_section(
            {
                "lane_status": "PASS",
                "source_count": 1,
                "publishable_candidates": 1,
                "selected_count": 1,
                "selected": [
                    {
                        "situation": "# [click](javascript:alert(1)) <script>x</script>",
                        "score": 0.5,
                        "source_repository": "acme/cml",
                        "registry_commit": PIN,
                        "pack_id": "e" * 64,
                        "selected_path": ["*bold*", "[link](https://example.invalid)"],
                    }
                ],
            }
        )
        self.assertNotIn("<script>", section)
        self.assertNotIn("[click](", section)
        self.assertNotIn("[link](", section)
        self.assertIn("\\[click\\]\\(", section)
        self.assertIn("&lt;script&gt;", section)

    def test_not_run_section_explains_exact_head_gate(self) -> None:
        section = integration.render_cml_section(
            {
                "lane_status": "NOT_RUN",
                "source_count": 1,
                "publishable_candidates": 0,
                "selected_count": 0,
                "selected": [],
            }
        )
        self.assertIn("initial exact-head gate failed", section)


if __name__ == "__main__":
    unittest.main()
