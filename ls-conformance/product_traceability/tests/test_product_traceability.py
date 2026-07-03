import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "validate.py"
spec = importlib.util.spec_from_file_location("product_trace_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)

FIXTURE = ROOT / "fixtures" / "robys_first_scroll_flicker.pending.json"
SCHEMA = ROOT / "schema.json"


class ProductTraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_reference_fixture_passes_full_validation(self):
        validator.validate_file(FIXTURE, SCHEMA)

    def test_rejects_candidate_mutated_after_decision(self):
        changed = copy.deepcopy(self.bundle)
        changed["candidate"]["hypothesis"] += " Mutated."
        with self.assertRaisesRegex(
            validator.TraceValidationError, "contentDigest"
        ):
            validator.validate_semantics(changed)

    def test_rejects_non_independent_approval(self):
        changed = copy.deepcopy(self.bundle)
        changed["decision"]["independence"]["isIndependent"] = False
        with self.assertRaisesRegex(
            validator.TraceValidationError, "independent"
        ):
            validator.validate_semantics(changed)

    def test_rejects_adoption_without_implementation(self):
        changed = copy.deepcopy(self.bundle)
        changed["record"]["status"] = "ADOPTED"
        changed["snapshot"]["unresolvedCandidateRefs"] = []
        changed["snapshot"]["activeRecordRefs"] = [changed["record"]["id"]]
        with self.assertRaisesRegex(
            validator.TraceValidationError, "requires implementation"
        ):
            validator.validate_semantics(changed)

    def test_rejects_adoption_without_exact_record_bindings(self):
        changed = copy.deepcopy(self.bundle)
        changed["implementation"] = {
            "id": "PIMPL-ROBYS-FIRST-SCROLL-001",
            "repository": "example/robys",
            "prNumber": 1,
            "headSha": "a" * 40,
            "files": ["src/page.tsx"],
            "status": "VERIFIED",
        }
        changed["evidence"] = [
            {
                "id": "PEVD-ROBYS-FIRST-SCROLL-001",
                "kind": "automated_test",
                "capturedAt": "2026-07-04T10:00:00+03:00",
                "producer": "qa-observer",
                "locator": "test:first-scroll",
                "supports": "No flicker in ten cold-cache runs",
                "confidence": 0.95,
            }
        ]
        changed["outcome"] = {
            "id": "POUT-ROBYS-FIRST-SCROLL-001",
            "assessedAt": "2026-07-04T10:10:00+03:00",
            "candidateRef": changed["candidate"]["id"],
            "status": "CONFIRMED",
            "evidenceRefs": ["PEVD-ROBYS-FIRST-SCROLL-001"],
            "observedOutcome": "No flicker observed",
        }
        changed["record"]["status"] = "ADOPTED"
        changed["snapshot"]["unresolvedCandidateRefs"] = []
        changed["snapshot"]["activeRecordRefs"] = [changed["record"]["id"]]

        with self.assertRaisesRegex(
            validator.TraceValidationError, "implementationRef"
        ):
            validator.validate_semantics(changed)

    def test_rejects_outcome_with_missing_evidence(self):
        changed = copy.deepcopy(self.bundle)
        changed["outcome"] = {
            "id": "POUT-ROBYS-FIRST-SCROLL-001",
            "assessedAt": "2026-07-04T10:00:00+03:00",
            "candidateRef": changed["candidate"]["id"],
            "status": "CONFIRMED",
            "evidenceRefs": ["PEVD-MISSING-001"],
            "observedOutcome": "No flicker observed",
        }
        with self.assertRaisesRegex(
            validator.TraceValidationError, "missing evidence"
        ):
            validator.validate_semantics(changed)

    def test_rejects_snapshot_that_drops_durable_record(self):
        changed = copy.deepcopy(self.bundle)
        changed["snapshot"]["sourceRecordRefs"] = []
        with self.assertRaisesRegex(
            validator.TraceValidationError, "must include record.id"
        ):
            validator.validate_semantics(changed)

    def test_rejects_active_record_missing_from_active_snapshot(self):
        changed = copy.deepcopy(self.bundle)
        changed["record"]["status"] = "EXPERIMENT_ACTIVE"
        with self.assertRaisesRegex(
            validator.TraceValidationError, "exactly reflect active"
        ):
            validator.validate_semantics(changed)

    def test_rejects_nonterminal_candidate_missing_from_unresolved_snapshot(self):
        changed = copy.deepcopy(self.bundle)
        changed["snapshot"]["unresolvedCandidateRefs"] = []
        with self.assertRaisesRegex(
            validator.TraceValidationError, "exactly reflect candidate resolution"
        ):
            validator.validate_semantics(changed)

    def test_more_evidence_decision_cannot_create_record(self):
        changed = copy.deepcopy(self.bundle)
        changed["decision"]["verdict"] = "REQUEST_MORE_EVIDENCE"
        with self.assertRaisesRegex(
            validator.TraceValidationError, "must not fabricate"
        ):
            validator.validate_semantics(changed)

    def test_full_validation_rejects_malformed_datetime(self):
        changed = copy.deepcopy(self.bundle)
        changed["signal"]["observedAt"] = "not-a-date-time"
        with tempfile.TemporaryDirectory() as directory:
            bundle_path = Path(directory) / "bundle.json"
            bundle_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(
                validator.TraceValidationError, "JSON Schema validation failed"
            ):
                validator.validate_file(bundle_path, SCHEMA)


if __name__ == "__main__":
    unittest.main()
