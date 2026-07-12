import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from ls_audit import InputError, Ref, parse_url, run, validate_sha

HEAD, OTHER = "a" * 40, "b" * 40


class Fake:
    def __init__(self, observed: str = HEAD) -> None:
        self.observed = observed

    def get(self, endpoint: str) -> Any:
        if endpoint.endswith("/pulls/7"):
            return {"html_url": "https://github.com/acme/widget/pull/7", "number": 7, "title": "change",
                    "state": "open", "draft": False, "user": {"login": "agent"},
                    "head": {"sha": self.observed, "ref": "agent/change"},
                    "base": {"sha": "c" * 40, "ref": "main"}, "changed_files": 1, "additions": 2, "deletions": 1}
        if endpoint.endswith(f"/commits/{HEAD}/status"):
            return {"state": "success"}
        if endpoint.endswith(f"/commits/{HEAD}/check-runs?per_page=100"):
            return {"check_runs": [{"name": "tests", "app": {"slug": "actions"},
                                     "status": "completed", "conclusion": "success"}]}
        raise AssertionError(endpoint)

    def pages(self, endpoint: str) -> list[Any]:
        if endpoint.endswith("/files"):
            return [{"filename": "payments.py", "status": "modified", "patch": "@@"}]
        if endpoint.endswith("/reviews"):
            return [{"id": 1, "user": {"login": "bot"}, "state": "COMMENTED", "commit_id": HEAD}]
        raise AssertionError(endpoint)


class Tests(unittest.TestCase):
    def test_inputs(self) -> None:
        self.assertEqual(parse_url("https://github.com/acme/widget/pull/7"), Ref("github.com", "acme", "widget", 7))
        with self.assertRaises(InputError):
            validate_sha("abc")

    def test_bundle_without_adjudication_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "bundle"
            result = run("https://github.com/acme/widget/pull/7", HEAD, out, Fake())
            self.assertEqual(result.exit_code, 0)
            card = json.loads((out / "scorecard.json").read_text())
            self.assertIn("HUMAN ADJUDICATION", card["verdict"])
            self.assertTrue((out / "adjudication-template.json").exists())

    def test_mismatch_stops_secondary_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "bundle"
            result = run("https://github.com/acme/widget/pull/7", HEAD, out, Fake(OTHER))
            self.assertEqual(result.exit_code, 3)
            self.assertFalse((out / "evidence/files.json").exists())
            self.assertEqual(json.loads((out / "scorecard.json").read_text())["verdict"], "HOLD")

    def test_human_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adj = root / "adj.json"
            adj.write_text(json.dumps({"schema_version": "ls.human-adjudication.v0.1",
                "target": {"pr_url": "https://github.com/acme/widget/pull/7", "expected_head": HEAD},
                "reviewer": "maintainer", "decision": "PASS", "summary": "bounded risk accepted",
                "accepted_incomplete_lanes": [], "findings": []}))
            result = run("https://github.com/acme/widget/pull/7", HEAD, root / "bundle", Fake(), adjudication_path=adj)
            self.assertEqual(result.verdict, "PASS — HUMAN ADJUDICATED")

    def test_wrong_adjudication_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adj = root / "adj.json"
            adj.write_text(json.dumps({"schema_version": "ls.human-adjudication.v0.1",
                "target": {"pr_url": "https://github.com/acme/other/pull/7", "expected_head": HEAD},
                "reviewer": "maintainer", "decision": "PASS", "summary": "wrong",
                "accepted_incomplete_lanes": [], "findings": []}))
            with self.assertRaises(InputError):
                run("https://github.com/acme/widget/pull/7", HEAD, root / "bundle", Fake(), adjudication_path=adj)


if __name__ == "__main__":
    unittest.main()
