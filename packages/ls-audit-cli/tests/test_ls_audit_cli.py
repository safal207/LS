import json
import tempfile
import unittest
from pathlib import Path

from ls_audit import InputError
from ls_audit_cli import harden_scorecard, review_submission_state, validate_finding_dispositions

HEAD = "a" * 40


class PolicyTests(unittest.TestCase):
    def test_review_submission_states(self) -> None:
        self.assertEqual(review_submission_state([], HEAD), "NOT_RUN")
        self.assertEqual(review_submission_state(None, HEAD), "INCOMPLETE")
        self.assertEqual(review_submission_state([{"commit_id": "b" * 40, "state": "APPROVED"}], HEAD), "INCOMPLETE")
        self.assertEqual(review_submission_state([{"commit_id": HEAD, "state": "COMMENTED"}], HEAD), "INCOMPLETE")
        self.assertEqual(review_submission_state([{"commit_id": HEAD, "state": "APPROVED"}], HEAD), "PASS")
        self.assertEqual(review_submission_state([{"commit_id": HEAD, "state": "CHANGES_REQUESTED"}], HEAD), "FAIL")

    def test_changes_requested_overrides_approval(self) -> None:
        reviews = [
            {"commit_id": HEAD, "state": "APPROVED"},
            {"commit_id": HEAD, "state": "CHANGES_REQUESTED"},
        ]
        self.assertEqual(review_submission_state(reviews, HEAD), "FAIL")

    def test_harden_scorecard_holds_changes_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            evidence = output / "evidence"
            evidence.mkdir()
            (evidence / "reviews.json").write_text(json.dumps([
                {"commit_id": HEAD, "state": "CHANGES_REQUESTED"}
            ]))
            (output / "scorecard.json").write_text(json.dumps({
                "target": {"expected_head": HEAD, "pr_url": "https://github.com/acme/repo/pull/1"},
                "lanes": {"exact_head": "PASS", "exact_head_reviews": "PASS", "human_adjudication": "NOT_RUN"},
                "adjudication": None,
                "evidence_digests": {},
                "interpretation": "",
                "verdict": "INCOMPLETE",
            }))
            result = harden_scorecard(output)
            self.assertEqual(result.verdict, "HOLD")
            card = json.loads((output / "scorecard.json").read_text())
            self.assertEqual(card["lanes"]["exact_head_review_submissions"], "FAIL")
            self.assertNotIn("exact_head_reviews", card["lanes"])

    def test_invalid_finding_disposition_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "adjudication.json"
            path.write_text(json.dumps({"findings": [{"disposition": "accepted"}]}))
            with self.assertRaises(InputError):
                validate_finding_dispositions(path)


if __name__ == "__main__":
    unittest.main()
