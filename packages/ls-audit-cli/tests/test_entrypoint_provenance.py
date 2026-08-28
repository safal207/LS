import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ls_audit as core
import ls_audit_entrypoint as entrypoint

HEAD = "a" * 40


class ProvenanceTests(unittest.TestCase):
    def write_bundle(self, root: Path) -> None:
        evidence_digests = {"evidence/pr.json": "1" * 64}
        scorecard = {
            "schema_version": core.SCHEMA,
            "generated_at": "2026-07-27T00:00:00Z",
            "target": {
                "pr_url": "https://github.com/acme/widget/pull/7",
                "expected_head": HEAD,
                "observed_head": HEAD,
            },
            "verdict": "INCOMPLETE — HUMAN ADJUDICATION REQUIRED",
            "lanes": {"exact_head": "PASS", "human_adjudication": "NOT_RUN"},
            "interpretation": "bounded",
            "evidence_digests": evidence_digests,
            "bundle_digest": "sha256:" + "0" * 64,
            "authority": "advisory-only",
            "adjudication": None,
        }
        manifest = {
            "schema_version": core.SCHEMA,
            "tool": {"name": "ls-exact-head-audit", "version": "0.2.0"},
            "generated_at": "2026-07-27T00:00:00Z",
            "target": scorecard["target"],
            "authority": "advisory-only",
            "evidence_digests": evidence_digests,
            "bundle_digest": scorecard["bundle_digest"],
        }
        core.write_json(root / "scorecard.json", scorecard)
        core.write_json(root / "manifest.json", manifest)
        (root / "SCORECARD.md").write_text("old", encoding="utf-8")

    def test_tool_source_is_bound_into_manifest_scorecard_and_bundle_digest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_bundle(root)
            env = {
                "GITHUB_REPOSITORY": "safal207/LS",
                "GITHUB_WORKFLOW": "LS Exact-Head Audit CLI",
                "GITHUB_RUN_ID": "123456",
                "GITHUB_RUN_ATTEMPT": "2",
            }
            with patch.dict(os.environ, env, clear=False):
                entrypoint.stamp_tool_provenance(root, HEAD)

            manifest = json.loads((root / "manifest.json").read_text())
            scorecard = json.loads((root / "scorecard.json").read_text())
            self.assertEqual(manifest["tool"]["source_sha"], HEAD)
            self.assertEqual(manifest["tool"]["source_repository"], "safal207/LS")
            self.assertEqual(manifest["tool"]["workflow_run_id"], 123456)
            self.assertEqual(manifest["tool"]["workflow_run_attempt"], 2)
            self.assertEqual(scorecard["tool"], manifest["tool"])
            self.assertEqual(scorecard["bundle_digest"], manifest["bundle_digest"])
            self.assertEqual(
                manifest["scorecard_digests"]["scorecard.json"],
                hashlib.sha256((root / "scorecard.json").read_bytes()).hexdigest(),
            )
            self.assertEqual(
                manifest["scorecard_digests"]["SCORECARD.md"],
                hashlib.sha256((root / "SCORECARD.md").read_bytes()).hexdigest(),
            )

    def test_invalid_tool_source_sha_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_bundle(root)
            with self.assertRaises(core.InputError):
                entrypoint.stamp_tool_provenance(root, "main")

    def test_explicit_source_repository_matches_the_owner_of_source_sha(self) -> None:
        env = {
            "GITHUB_REPOSITORY": "upstream/LS",
            "LS_TOOL_SOURCE_REPOSITORY": "contributor/LS",
        }
        with patch.dict(os.environ, env, clear=False):
            metadata = entrypoint._tool_metadata(HEAD)

        self.assertEqual(metadata["source_sha"], HEAD)
        self.assertEqual(metadata["source_repository"], "contributor/LS")

    def test_output_path_supports_default_explicit_and_reordered_forms(self) -> None:
        default = entrypoint._output_path(
            [
                "https://github.com/acme/widget/pull/7",
                "--expected-head",
                HEAD,
            ]
        )
        self.assertEqual(default, Path(f"ls-audit-acme-widget-pr-7-{HEAD[:12]}"))
        self.assertEqual(
            entrypoint._output_path(
                [
                    "https://github.com/acme/widget/pull/7",
                    f"--expected-head={HEAD}",
                    "--output=/tmp/bundle",
                ]
            ),
            Path("/tmp/bundle"),
        )
        self.assertEqual(
            entrypoint._output_path(
                [
                    "--expected-head",
                    HEAD,
                    "--output",
                    "/tmp/reordered",
                    "https://github.com/acme/widget/pull/7",
                ]
            ),
            Path("/tmp/reordered"),
        )


if __name__ == "__main__":
    unittest.main()
