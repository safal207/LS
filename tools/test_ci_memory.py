#!/usr/bin/env python3
"""Regression tests for tools/ci_memory.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ci_memory


class CIMemoryTest(unittest.TestCase):
    def harmony_axis(self) -> dict[str, object]:
        return {
            "balance": "STRONG_HARMONY",
            "project": "HARMONY",
            "intermediate": "HARMONY",
            "realization": "STRONG_HARMONY",
            "chaos_sources": [
                "schema-valid but audit-provenance-invalid LS response artifact",
                "cross-PR source mismatch",
            ],
            "harmony_mechanisms": [
                "append-only CI memory event",
                "temporal replay ordered by observed_at",
            ],
            "transition": "PR #831 provenance chaos became a replayable CI memory guardrail.",
        }

    def trajectory_axis(self) -> dict[str, object]:
        return {
            "from_state": "UNTRACKED_PROVENANCE_CHAOS",
            "to_state": "REPLAYABLE_CI_MEMORY_GUARDRAIL",
            "direction": "CHAOS_TO_HARMONY",
            "phase": "STABILIZATION",
            "phase_order": 6,
            "transition_path": [
                "DRIFT",
                "COLLISION",
                "CAPTURE",
                "TRANSLATION",
                "REPLAY",
                "STABILIZATION",
            ],
            "trajectory_summary": "The PR #831 provenance mismatch moved from hidden audit risk into deterministic CI memory.",
        }

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
            "harmony_axis": self.harmony_axis(),
            "trajectory_axis": self.trajectory_axis(),
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
        self.assertEqual(report["timeline"][0]["harmony_balance"], "STRONG_HARMONY")
        self.assertEqual(report["timeline"][0]["trajectory_direction"], "CHAOS_TO_HARMONY")
        self.assertEqual(report["timeline"][0]["trajectory_phase"], "STABILIZATION")
        self.assertEqual(
            report["known_failure_ids"],
            ["pr831-provenance-mismatch-v0.1"],
        )

    def test_replay_emits_harmony_axis_summary(self) -> None:
        report = ci_memory.replay_events([self.pr831_event()])
        self.assertEqual(report["harmony_axis"][0]["event_id"], "pr831-provenance-mismatch-v0.1")
        self.assertEqual(report["harmony_axis"][0]["balance"], "STRONG_HARMONY")
        self.assertEqual(report["harmony_axis"][0]["project"], "HARMONY")
        self.assertIn(
            "cross-PR source mismatch",
            report["harmony_axis"][0]["chaos_sources"],
        )

    def test_replay_emits_trajectory_axis_summary(self) -> None:
        report = ci_memory.replay_events([self.pr831_event()])
        self.assertEqual(report["trajectory_axis"][0]["event_id"], "pr831-provenance-mismatch-v0.1")
        self.assertEqual(report["trajectory_axis"][0]["from_state"], "UNTRACKED_PROVENANCE_CHAOS")
        self.assertEqual(report["trajectory_axis"][0]["to_state"], "REPLAYABLE_CI_MEMORY_GUARDRAIL")
        self.assertEqual(report["trajectory_axis"][0]["direction"], "CHAOS_TO_HARMONY")
        self.assertEqual(report["trajectory_axis"][0]["phase"], "STABILIZATION")
        self.assertEqual(report["trajectory_axis"][0]["phase_order"], 6)

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

    def test_invalid_harmony_balance_is_rejected(self) -> None:
        event = self.pr831_event()
        harmony_axis = event["harmony_axis"]
        self.assertIsInstance(harmony_axis, dict)
        harmony_axis["balance"] = "COSMIC_VIBES"
        errors = ci_memory.validate_event(event)
        self.assertIn(
            "harmony_axis.balance must be one of ['CHAOS', 'HARMONY', 'MIXED', 'STRONG_HARMONY']",
            errors,
        )

    def test_missing_harmony_axis_is_rejected(self) -> None:
        event = self.pr831_event()
        del event["harmony_axis"]
        errors = ci_memory.validate_event(event)
        self.assertIn("missing fields: ['harmony_axis']", errors)
        self.assertIn("harmony_axis must be an object", errors)

    def test_invalid_trajectory_direction_is_rejected(self) -> None:
        event = self.pr831_event()
        trajectory_axis = event["trajectory_axis"]
        self.assertIsInstance(trajectory_axis, dict)
        trajectory_axis["direction"] = "SIDEWAYS_SPIRAL"
        errors = ci_memory.validate_event(event)
        self.assertIn(
            "trajectory_axis.direction must be one of ['CHAOS_TO_HARMONY', 'HARMONY_TO_CHAOS', 'MIXED_TRANSITION', 'STABLE_CHAOS', 'STABLE_HARMONY']",
            errors,
        )

    def test_invalid_trajectory_phase_order_is_rejected(self) -> None:
        event = self.pr831_event()
        trajectory_axis = event["trajectory_axis"]
        self.assertIsInstance(trajectory_axis, dict)
        trajectory_axis["phase_order"] = 5
        errors = ci_memory.validate_event(event)
        self.assertIn("trajectory_axis.phase_order must be 6 for phase STABILIZATION", errors)

    def test_invalid_trajectory_path_order_is_rejected(self) -> None:
        event = self.pr831_event()
        trajectory_axis = event["trajectory_axis"]
        self.assertIsInstance(trajectory_axis, dict)
        trajectory_axis["transition_path"] = ["DRIFT", "REPLAY", "CAPTURE", "STABILIZATION"]
        errors = ci_memory.validate_event(event)
        self.assertIn("trajectory_axis.transition_path must be strictly ordered by phase", errors)

    def test_invalid_trajectory_path_end_is_rejected(self) -> None:
        event = self.pr831_event()
        trajectory_axis = event["trajectory_axis"]
        self.assertIsInstance(trajectory_axis, dict)
        trajectory_axis["transition_path"] = ["DRIFT", "COLLISION", "CAPTURE"]
        errors = ci_memory.validate_event(event)
        self.assertIn("trajectory_axis.transition_path must end with trajectory_axis.phase", errors)

    def test_missing_trajectory_axis_is_rejected(self) -> None:
        event = self.pr831_event()
        del event["trajectory_axis"]
        errors = ci_memory.validate_event(event)
        self.assertIn("missing fields: ['trajectory_axis']", errors)
        self.assertIn("trajectory_axis must be an object", errors)

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
                '  "evidence": ["audits/ls-responses/pr824/ls_response.json"],\n'
                '  "harmony_axis": {\n'
                '    "balance": "STRONG_HARMONY",\n'
                '    "project": "HARMONY",\n'
                '    "intermediate": "HARMONY",\n'
                '    "realization": "STRONG_HARMONY",\n'
                '    "chaos_sources": ["cross-PR source mismatch"],\n'
                '    "harmony_mechanisms": ["append-only CI memory event"],\n'
                '    "transition": "chaos became replayable CI memory"\n'
                '  },\n'
                '  "trajectory_axis": {\n'
                '    "from_state": "UNTRACKED_PROVENANCE_CHAOS",\n'
                '    "to_state": "REPLAYABLE_CI_MEMORY_GUARDRAIL",\n'
                '    "direction": "CHAOS_TO_HARMONY",\n'
                '    "phase": "STABILIZATION",\n'
                '    "phase_order": 6,\n'
                '    "transition_path": ["DRIFT", "COLLISION", "CAPTURE", "TRANSLATION", "REPLAY", "STABILIZATION"],\n'
                '    "trajectory_summary": "chaos became a CI guardrail"\n'
                '  }\n'
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
