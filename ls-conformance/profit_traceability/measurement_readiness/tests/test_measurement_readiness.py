import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "validate.py"
spec = importlib.util.spec_from_file_location("measurement_readiness_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)

FIXTURE = ROOT / "fixtures" / "robys_menu_to_visit.instrumentation_required.json"
SCHEMA = ROOT / "schema.json"


class MeasurementReadinessTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def ready_bundle(self):
        changed = copy.deepcopy(self.bundle)
        changed["measurementPlan"]["status"] = "READY_FOR_BASELINE"
        changed["measurementPlan"]["blockers"] = []
        changed["implementation"] = {
            "id": "MIMPL-ROBYS-MENU-TO-VISIT-001",
            "repository": "example/robys",
            "prNumber": 1,
            "headSha": "a" * 40,
            "files": ["src/attribution.ts", "src/pos-export.ts"],
            "status": "VERIFIED",
        }
        changed["evidence"] = [
            {
                "id": "MEVD-ROBYS-INSTRUMENTATION-001",
                "kind": "instrumentation_test",
                "capturedAt": "2026-07-04T10:00:00+03:00",
                "producer": "qa-observer",
                "locator": "test:visit-token",
                "supports": "Token is issued and persisted without PII",
                "confidence": 0.95,
                "implementationRef": "MIMPL-ROBYS-MENU-TO-VISIT-001",
                "headSha": "a" * 40,
            },
            {
                "id": "MEVD-ROBYS-JOIN-001",
                "kind": "join_integrity",
                "capturedAt": "2026-07-04T10:05:00+03:00",
                "producer": "qa-observer",
                "locator": "test:pos-join",
                "supports": "Web token joins exactly one POS order",
                "confidence": 0.95,
                "implementationRef": "MIMPL-ROBYS-MENU-TO-VISIT-001",
                "headSha": "a" * 40,
            },
        ]
        changed["readinessDecision"] = {
            "planRef": changed["measurementPlan"]["id"],
            "implementationRef": changed["implementation"]["id"],
            "status": "READY_FOR_BASELINE",
            "reason": "Verified instrumentation and POS join evidence are present.",
            "evidenceRefs": [
                "MEVD-ROBYS-INSTRUMENTATION-001",
                "MEVD-ROBYS-JOIN-001",
            ],
        }
        changed["snapshot"]["activePlanRefs"] = [changed["measurementPlan"]["id"]]
        changed["snapshot"]["blockedPlanRefs"] = []
        return changed

    def test_blocked_fixture_passes_full_validation(self):
        validator.validate_file(FIXTURE, SCHEMA)

    def test_ready_bundle_passes(self):
        validator.validate_semantics(self.ready_bundle())

    def test_rejects_candidate_binding_mismatch(self):
        changed = copy.deepcopy(self.bundle)
        changed["decisionBinding"]["candidateRef"] = "ECOHYP-OTHER-001"
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "candidateRef"
        ):
            validator.validate_semantics(changed)

    def test_rejects_pii_collection(self):
        changed = copy.deepcopy(self.bundle)
        changed["measurementPlan"]["tokenContract"]["collectsPII"] = True
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "must not collect PII"
        ):
            validator.validate_semantics(changed)

    def test_rejects_token_ttl_mismatch(self):
        changed = copy.deepcopy(self.bundle)
        changed["measurementPlan"]["tokenContract"]["ttlHours"] = 48
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "TTL"
        ):
            validator.validate_semantics(changed)

    def test_rejects_missing_pos_join_field(self):
        changed = copy.deepcopy(self.bundle)
        changed["measurementPlan"]["posContract"]["requiredFields"].remove(
            "campaign_token"
        )
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "missing required fields"
        ):
            validator.validate_semantics(changed)

    def test_ready_requires_verified_implementation(self):
        changed = self.ready_bundle()
        changed["implementation"]["status"] = "IMPLEMENTED"
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "VERIFIED implementation"
        ):
            validator.validate_semantics(changed)

    def test_ready_requires_join_evidence(self):
        changed = self.ready_bundle()
        changed["readinessDecision"]["evidenceRefs"] = [
            "MEVD-ROBYS-INSTRUMENTATION-001"
        ]
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "join_integrity"
        ):
            validator.validate_semantics(changed)

    def test_baseline_complete_requires_export_and_cost_evidence(self):
        changed = self.ready_bundle()
        changed["measurementPlan"]["status"] = "BASELINE_COMPLETE"
        changed["readinessDecision"]["status"] = "BASELINE_COMPLETE"
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "baseline_export"
        ):
            validator.validate_semantics(changed)

    def test_snapshot_cannot_drop_plan(self):
        changed = copy.deepcopy(self.bundle)
        changed["snapshot"]["sourcePlanRefs"] = []
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "must include plan.id"
        ):
            validator.validate_semantics(changed)

    def test_rejects_stale_head_evidence(self):
        changed = self.ready_bundle()
        changed["evidence"][0]["headSha"] = "b" * 40
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "exact implementation headSha"
        ):
            validator.validate_semantics(changed)

    def test_rejects_unknown_snapshot_plan(self):
        changed = copy.deepcopy(self.bundle)
        changed["snapshot"]["sourcePlanRefs"].append("MPLAN-UNKNOWN-001")
        with self.assertRaisesRegex(
            validator.MeasurementReadinessValidationError, "unknown plans"
        ):
            validator.validate_semantics(changed)

    def test_full_validation_rejects_malformed_datetime(self):
        changed = copy.deepcopy(self.bundle)
        changed["measurementPlan"]["createdAt"] = "not-a-date-time"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(
                validator.MeasurementReadinessValidationError,
                "JSON Schema validation failed",
            ):
                validator.validate_file(path, SCHEMA)


if __name__ == "__main__":
    unittest.main()
