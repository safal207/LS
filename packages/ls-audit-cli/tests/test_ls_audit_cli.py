import json
import tempfile
import unittest
from pathlib import Path

from ls_audit import ApiError, InputError, Ref
from ls_audit_cli import (
    harden_scorecard,
    record_final_head,
    review_submission_state,
    validate_finding_dispositions,
    validate_network_boundary,
    validate_output_boundary,
    policy_verdict,
    cleanup_unsealed,
)

HEAD = "a" * 40


class Client:
    def __init__(self, observed=HEAD, error=False):
        self.observed = observed
        self.error = error

    def get(self, endpoint):
        if self.error:
            raise ApiError(endpoint, 503, "unavailable")
        return {"head": {"sha": self.observed}}


class PolicyTests(unittest.TestCase):
    def test_review_submission_states(self) -> None:
        self.assertEqual(review_submission_state([], HEAD), "NOT_RUN")
        self.assertEqual(review_submission_state(None, HEAD), "INCOMPLETE")
        self.assertEqual(review_submission_state([{"commit_id": "b" * 40, "state": "APPROVED"}], HEAD), "INCOMPLETE")
        self.assertEqual(review_submission_state([{"commit_id": HEAD, "state": "COMMENTED"}], HEAD), "INCOMPLETE")
        self.assertEqual(review_submission_state([{"commit_id": HEAD, "state": "APPROVED"}], HEAD), "PASS")
        self.assertEqual(review_submission_state([{"commit_id": HEAD, "state": "CHANGES_REQUESTED"}], HEAD), "FAIL")

    def test_latest_review_per_reviewer_controls_state(self) -> None:
        resolved = [
            {"id": 1, "reviewer": "alice", "submitted_at": "2026-01-01T00:00:00Z", "commit_id": HEAD, "state": "CHANGES_REQUESTED"},
            {"id": 2, "reviewer": "alice", "submitted_at": "2026-01-02T00:00:00Z", "commit_id": HEAD, "state": "APPROVED"},
        ]
        self.assertEqual(review_submission_state(resolved, HEAD), "PASS")
        blocked = list(reversed(resolved))
        blocked[0] = {"id": 3, "reviewer": "alice", "submitted_at": "2026-01-03T00:00:00Z", "commit_id": HEAD, "state": "CHANGES_REQUESTED"}
        self.assertEqual(review_submission_state(blocked, HEAD), "FAIL")

    def test_identity_lanes_are_not_human_waivable(self) -> None:
        human = {
            "decision": "PASS",
            "accepted_incomplete_lanes": [{"lane": "final_exact_head", "reason": "manual acceptance"}],
        }
        lanes = {"exact_head": "PASS", "final_exact_head": "INCOMPLETE", "human_adjudication": "PASS"}
        self.assertEqual(policy_verdict(lanes, human), "INCONCLUSIVE — EXACT-HEAD EVIDENCE INCOMPLETE")

    def test_network_boundary_protects_token_target(self) -> None:
        self.assertEqual(validate_network_boundary(Ref("github.com", "a", "b", 1), None), "https://api.github.com")
        with self.assertRaises(InputError):
            validate_network_boundary(Ref("evil.example", "a", "b", 1), None)
        with self.assertRaises(InputError):
            validate_network_boundary(Ref("github.com", "a", "b", 1), "https://evil.example")

    def test_overwrite_requires_ls_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "data"
            output.mkdir()
            with self.assertRaises(InputError):
                validate_output_boundary(output, True)
            (output / "manifest.json").write_text(json.dumps({
                "schema_version": "ls.exact-head-audit.v0.1", "authority": "advisory-only"
            }))
            validate_output_boundary(output, True)

    def test_cleanup_removes_only_unsealed_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            unsealed = Path(temp) / "unsealed"
            unsealed.mkdir()
            (unsealed / "partial").write_text("x")
            cleanup_unsealed(unsealed)
            self.assertFalse(unsealed.exists())
            sealed = Path(temp) / "sealed"
            sealed.mkdir()
            (sealed / "manifest.json").write_text("{}")
            cleanup_unsealed(sealed)
            self.assertTrue(sealed.exists())

    def test_final_head_states(self) -> None:
        ref = Ref("github.com", "acme", "repo", 1)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "evidence").mkdir()
            state, _ = record_final_head(Client(), ref, HEAD, output)
            self.assertEqual(state, "PASS")
            state, _ = record_final_head(Client("b" * 40), ref, HEAD, output)
            self.assertEqual(state, "FAIL")
            state, _ = record_final_head(Client(error=True), ref, HEAD, output)
            self.assertEqual(state, "INCOMPLETE")

    def test_harden_scorecard_holds_changes_requested_and_binds_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            evidence = output / "evidence"
            evidence.mkdir()
            (evidence / "reviews.json").write_text(json.dumps([
                {"commit_id": HEAD, "state": "CHANGES_REQUESTED"}
            ]))
            (evidence / "pr.json").write_text(json.dumps({"changed_files": 0}))
            (evidence / "files.json").write_text("[]")
            (output / "manifest.json").write_text(json.dumps({
                "schema_version": "ls.exact-head-audit.v0.1",
                "authority": "advisory-only",
                "evidence_digests": {},
            }))
            (output / "scorecard.json").write_text(json.dumps({
                "target": {"expected_head": HEAD, "pr_url": "https://github.com/acme/repo/pull/1"},
                "lanes": {"exact_head": "PASS", "exact_head_reviews": "PASS", "human_adjudication": "NOT_RUN"},
                "adjudication": None,
                "evidence_digests": {},
                "interpretation": "",
                "verdict": "INCOMPLETE",
            }))
            final = {"expected_head": HEAD, "observed_head": HEAD, "status": "PASS"}
            digest = __import__("ls_audit").write_json(evidence / "final-head.json", final)
            result = harden_scorecard(output, "PASS", digest)
            self.assertEqual(result.verdict, "HOLD")
            card = json.loads((output / "scorecard.json").read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(card["lanes"]["exact_head_review_submissions"], "FAIL")
            self.assertEqual(card["lanes"]["final_exact_head"], "PASS")
            self.assertIn("scorecard_digests", manifest)

    def test_invalid_finding_disposition_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "adjudication.json"
            path.write_text(json.dumps({"findings": [{"disposition": "accepted"}]}))
            with self.assertRaises(InputError):
                validate_finding_dispositions(path)


if __name__ == "__main__":
    unittest.main()
