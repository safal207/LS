import copy
import importlib.util
import json
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

    def test_more_evidence_decision_cannot_create_record(self):
        changed = copy.deepcopy(self.bundle)
        changed["decision"]["verdict"] = "REQUEST_MORE_EVIDENCE"
        with self.assertRaisesRegex(
            validator.TraceValidationError, "must not fabricate"
        ):
            validator.validate_semantics(changed)


if __name__ == "__main__":
    unittest.main()
