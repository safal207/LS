#!/usr/bin/env python3
"""Regression tests for tools/ci_memory.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ci_memory


class CIMemoryTest(unittest.TestCase):
    def pr831_event(self) -> dict[str, object]:
        return {
            "schema_version": ci_memory.EVENT_SCHEMA_VERSION,
            "event_id": "pr831-provenance-mismatch-v0.1",
            "event_type": "PROVENANCE_MISMATCH",
            "observed_at": "2026-07-08T16:32:31Z",
            "observed_in_pr": 831,
            "subject": {
                "pr_number": 824,
                "commit_sha": "f1cfdfbf5f648bc28434fb2f5a0cb77eb7e86666",
            },
            "source": {
                "pr_number": 828,
                "head_sha": "0b953d3428adca691421dddd861e20e1c0213b47",
            },
            "decision": "BLOCK_MERGE",
            "evidence": [
                "audits/ls-responses/pr824/ls_response.json",
                ".github/workflows/ls-response-validation.yml",
                "tools/build_ls_audit_pack.py",
            ],
        }

    def test_pr831_event_is_valid_known_failure(self) -> None:
        event = self.pr831_event()
        self.assertEqual(ci_memory.validate_event(event), [])
        self.assertTrue(ci_memory.is_known_failure(event))

    def test_replay_emits_known_failure_status(self) -> None:
        report = ci_memory.replay_events([self.pr831_event()])
        self.assertEqual(report["status"], "KNOWN_FAILURE_REPLAYED")
        self.assertEqual(report["known_failures_count"], 1)
        self.assertEqual(report["invalid_events_count"], 0)
        self.assertEqual(
            report["known_failure_ids"],
            ["pr831-provenance-mismatch-v0.1"],
        )

    def test_duplicate_event_ids_are_rejected(self) -> None:
        report = ci_memory.replay_events([self.pr831_event(), self.pr831_event()])
        self.assertEqual(report["status"], "INVALID_EVENTS")
        self.assertFalse(report["validation"][1]["valid"])
        self.assertIn(
            "duplicate event_id: pr831-provenance-mismatch-v0.1",
            report["validation"][1]["errors"],
        )

    def test_invalid_decision_is_rejected(self) -> None:
        event = self.pr831_event()
        event["decision"] = "YOLO_MERGE"
        errors = ci_memory.validate_event(event)
        self.assertIn(
            "decision must be one of ['ALLOW_WITH_GUARDRAIL', 'BLOCK_MERGE', 'DOCUMENT_ONLY']",
            errors,
        )

    def test_invalid_observed_at_is_rejected(self) -> None:
        event = self.pr831_event()
        event["observed_at"] = "not-a-date"
        errors = ci_memory.validate_event(event)
        self.assertIn("observed_at must be an ISO-8601 datetime", errors)

    def test_events_replay_in_observed_at_order(self) -> None:
        later = self.pr831_event()
        earlier = self.pr831_event()
        later["event_id"] = "later"
        later["observed_at"] = "2026-07-08T16:32:31Z"
        earlier["event_id"] = "earlier"
        earlier["observed_at"] = "2026-07-08T12:55:43Z"

        report = ci_memory.replay_events([later, earlier])
        self.assertEqual(
            [item["event_id"] for item in report["timeline"]],
            ["earlier", "later"],
        )
        self.assertEqual(report["timeline"][0]["replay_index"], 1)
        self.assertEqual(report["validation"][0]["event_id"], "earlier")

    def test_invalid_json_file_does_not_crash_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_dir = root / "events"
            events_dir.mkdir()
            bad_path = events_dir / "bad.json"
            bad_path.write_text('{"schema_version": ', encoding="utf-8")

            events = ci_memory.load_events(events_dir)
            self.assertEqual(len(events), 1)
            report = ci_memory.replay_events(events)
            self.assertEqual(report["status"], "INVALID_EVENTS")
            self.assertEqual(report["invalid_events_count"], 1)
            self.assertIn("invalid JSON", report["validation"][0]["errors"][0])

    def test_non_object_json_file_does_not_crash_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_dir = root / "events"
            events_dir.mkdir()
            bad_path = events_dir / "array.json"
            bad_path.write_text("[]", encoding="utf-8")

            events = ci_memory.load_events(events_dir)
            report = ci_memory.replay_events(events)
            self.assertEqual(report["status"], "INVALID_EVENTS")
            self.assertIn("event must be an object", report["validation"][0]["errors"][0])

    def test_build_ci_memory_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_dir = root / "events"
            out_dir = root / "out"
            events_dir.mkdir()
            (events_dir / "pr831.json").write_text(
                '{\n'
                '  "schema_version": "ls.ci_memory_event.v0.1",\n'
                '  "event_id": "pr831-provenance-mismatch-v0.1",\n'
                '  "event_type": "PROVENANCE_MISMATCH",\n'
                '  "observed_at": "2026-07-08T16:32:31Z",\n'
                '  "observed_in_pr": 831,\n'
                '  "subject": {\n'
                '    "pr_number": 824,\n'
                '    "commit_sha": "f1cfdfbf5f648bc28434fb2f5a0cb77eb7e86666"\n'
                '  },\n'
                '  "source": {\n'
                '    "pr_number": 828,\n'
                '    "head_sha": "0b953d3428adca691421dddd861e20e1c0213b47"\n'
                '  },\n'
                '  "decision": "BLOCK_MERGE",\n'
                '  "evidence": ["audits/ls-responses/pr824/ls_response.json"]\n'
                '}\n',
                encoding="utf-8",
            )
            report = ci_memory.build_ci_memory(events_dir, out_dir)
            self.assertEqual(report["status"], "KNOWN_FAILURE_REPLAYED")
            self.assertTrue((out_dir / "ci_memory_events.ndjson").is_file())
            self.assertTrue((out_dir / "ci_memory_report.json").is_file())
            self.assertTrue((out_dir / "ci_memory_report.md").is_file())


if __name__ == "__main__":
    unittest.main()
