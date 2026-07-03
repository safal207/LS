import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "validate.py"
spec = importlib.util.spec_from_file_location("profit_trace_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)

FIXTURE = ROOT / "fixtures" / "robys_menu_to_visit.blocked.json"
SCHEMA = ROOT / "schema.json"


class ProfitTraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def confirmed_scale_bundle(self):
        changed = copy.deepcopy(self.bundle)
        changed["candidate"]["baseline"] = {
            "status": "MEASURED",
            "value": 10,
            "measurementWindow": "7 days before experiment",
        }
        changed["candidate"]["contentDigest"] = validator.canonical_digest(
            changed["candidate"]
        )
        changed["decision"]["candidateDigest"] = changed["candidate"][
            "contentDigest"
        ]
        changed["decision"]["verdict"] = "APPROVE_EXPERIMENT"
        changed["businessEvidence"] = [
            {
                "id": "BEVD-ROBYS-ANALYTICS-001",
                "kind": "analytics",
                "capturedAt": "2026-07-11T20:00:00+03:00",
                "producer": "analytics-agent",
                "locator": "analytics:campaign-001",
                "supports": "Tracked web actions and attributable orders",
                "confidence": 0.9,
            },
            {
                "id": "BEVD-ROBYS-POS-001",
                "kind": "pos",
                "capturedAt": "2026-07-11T20:05:00+03:00",
                "producer": "pos-export",
                "locator": "pos:campaign-001",
                "supports": "Attributable order revenue",
                "confidence": 0.95,
            },
            {
                "id": "BEVD-ROBYS-VARIABLE-001",
                "kind": "variable_cost",
                "capturedAt": "2026-07-11T20:10:00+03:00",
                "producer": "finance-review",
                "locator": "costs:variable-001",
                "supports": "Variable costs for attributable orders",
                "confidence": 0.9,
            },
            {
                "id": "BEVD-ROBYS-ACQUISITION-001",
                "kind": "acquisition_cost",
                "capturedAt": "2026-07-11T20:12:00+03:00",
                "producer": "finance-review",
                "locator": "costs:acquisition-001",
                "supports": "Acquisition costs for attributable orders",
                "confidence": 0.9,
            },
            {
                "id": "BEVD-ROBYS-EXPERIMENT-001",
                "kind": "experiment_cost",
                "capturedAt": "2026-07-11T20:15:00+03:00",
                "producer": "finance-review",
                "locator": "costs:experiment-001",
                "supports": "Experiment implementation costs",
                "confidence": 0.9,
            },
        ]
        changed["businessOutcome"] = {
            "id": "BOUT-ROBYS-MENU-TO-VISIT-001",
            "assessedAt": "2026-07-11T21:00:00+03:00",
            "candidateRef": changed["candidate"]["id"],
            "status": "CONFIRMED",
            "evidenceRefs": [
                "BEVD-ROBYS-ANALYTICS-001",
                "BEVD-ROBYS-POS-001",
            ],
            "currency": "TRY",
            "attributableOrders": 20,
            "attributableRevenue": 3000,
            "attributionMethod": "Tracked campaign token matched to POS order",
            "windowStart": "2026-07-04T00:00:00+03:00",
            "windowEnd": "2026-07-11T00:00:00+03:00",
        }
        changed["unitEconomics"] = {
            "id": "UECO-ROBYS-MENU-TO-VISIT-001",
            "calculatedAt": "2026-07-11T21:10:00+03:00",
            "outcomeRef": "BOUT-ROBYS-MENU-TO-VISIT-001",
            "status": "CONFIRMED",
            "evidenceRefs": [
                "BEVD-ROBYS-VARIABLE-001",
                "BEVD-ROBYS-ACQUISITION-001",
                "BEVD-ROBYS-EXPERIMENT-001",
            ],
            "currency": "TRY",
            "attributableRevenue": 3000,
            "variableCosts": 1500,
            "acquisitionCosts": 300,
            "experimentCosts": 200,
            "netContribution": 1000,
            "formulaVersion": "net-contribution.v0",
        }
        changed["record"] = {
            "id": "PREC-ECO-ROBYS-MENU-TO-VISIT-001",
            "status": "SCALE",
            "decisionRef": changed["decision"]["id"],
            "businessOutcomeRef": changed["businessOutcome"]["id"],
            "unitEconomicsRef": changed["unitEconomics"]["id"],
        }
        changed["snapshot"] = {
            "snapshotId": "PSNAP-ECO-ROBYS-002",
            "generatedAt": "2026-07-11T21:15:00+03:00",
            "activeRecordRefs": [changed["record"]["id"]],
            "unresolvedCandidateRefs": [],
            "sourceRecordRefs": [changed["record"]["id"]],
        }
        return changed

    def test_blocked_fixture_passes_full_validation(self):
        validator.validate_file(FIXTURE, SCHEMA)

    def test_confirmed_positive_scale_bundle_passes(self):
        validator.validate_semantics(self.confirmed_scale_bundle())

    def test_rejects_candidate_mutated_after_decision(self):
        changed = copy.deepcopy(self.bundle)
        changed["candidate"]["economicHypothesis"] += " Mutated."
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "contentDigest"
        ):
            validator.validate_semantics(changed)

    def test_unknown_baseline_cannot_contain_value(self):
        changed = copy.deepcopy(self.bundle)
        changed["candidate"]["baseline"]["value"] = 10
        changed["candidate"]["contentDigest"] = validator.canonical_digest(
            changed["candidate"]
        )
        changed["decision"]["candidateDigest"] = changed["candidate"][
            "contentDigest"
        ]
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "UNKNOWN baseline"
        ):
            validator.validate_semantics(changed)

    def test_rejected_decision_requires_rejected_record(self):
        changed = self.confirmed_scale_bundle()
        changed["decision"]["verdict"] = "REJECT"
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "requires APPROVE_EXPERIMENT"
        ):
            validator.validate_semantics(changed)

    def test_rejected_record_requires_rejected_decision(self):
        changed = self.confirmed_scale_bundle()
        changed["record"]["status"] = "REJECTED"
        changed["snapshot"]["activeRecordRefs"] = []
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "requires a REJECT decision"
        ):
            validator.validate_semantics(changed)

    def test_more_evidence_cannot_create_record(self):
        changed = copy.deepcopy(self.bundle)
        changed["record"] = {
            "id": "PREC-ECO-ROBYS-MENU-TO-VISIT-001",
            "status": "EXPERIMENT_APPROVED",
            "decisionRef": changed["decision"]["id"],
        }
        changed["snapshot"]["sourceRecordRefs"] = [changed["record"]["id"]]
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "must not create a record"
        ):
            validator.validate_semantics(changed)

    def test_more_evidence_cannot_create_outcome(self):
        changed = copy.deepcopy(self.bundle)
        changed["businessOutcome"] = {
            "id": "BOUT-ROBYS-MENU-TO-VISIT-001",
            "assessedAt": "2026-07-04T03:00:00+03:00",
            "candidateRef": changed["candidate"]["id"],
            "status": "PENDING",
            "evidenceRefs": [],
            "currency": "TRY",
            "attributableOrders": 0,
            "attributableRevenue": 0,
            "attributionMethod": "Not yet measured",
            "windowStart": "2026-07-04T00:00:00+03:00",
            "windowEnd": "2026-07-05T00:00:00+03:00",
        }
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "must not create a businessOutcome"
        ):
            validator.validate_semantics(changed)

    def test_outcome_cannot_reference_missing_evidence(self):
        changed = self.confirmed_scale_bundle()
        changed["businessOutcome"]["evidenceRefs"].append("BEVD-MISSING-001")
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "missing evidence"
        ):
            validator.validate_semantics(changed)

    def test_confirmed_outcome_requires_attribution_evidence(self):
        changed = self.confirmed_scale_bundle()
        changed["businessOutcome"]["evidenceRefs"] = ["BEVD-ROBYS-POS-001"]
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "attribution evidence"
        ):
            validator.validate_semantics(changed)

    def test_confirmed_outcome_requires_revenue_evidence(self):
        changed = self.confirmed_scale_bundle()
        changed["businessOutcome"]["evidenceRefs"] = [
            "BEVD-ROBYS-ANALYTICS-001"
        ]
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "revenue evidence"
        ):
            validator.validate_semantics(changed)

    def test_rejects_currency_mismatch(self):
        changed = self.confirmed_scale_bundle()
        changed["unitEconomics"]["currency"] = "USD"
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "currencies must match"
        ):
            validator.validate_semantics(changed)

    def test_rejects_incorrect_net_contribution_formula(self):
        changed = self.confirmed_scale_bundle()
        changed["unitEconomics"]["netContribution"] = 1500
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "net-contribution.v0"
        ):
            validator.validate_semantics(changed)

    def test_confirmed_economics_requires_each_included_cost_evidence(self):
        changed = self.confirmed_scale_bundle()
        changed["unitEconomics"]["evidenceRefs"].remove(
            "BEVD-ROBYS-ACQUISITION-001"
        )
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "acquisition_cost evidence"
        ):
            validator.validate_semantics(changed)

    def test_excluded_cost_must_be_zero(self):
        changed = self.confirmed_scale_bundle()
        changed["candidate"]["costModel"]["includeAcquisitionCosts"] = False
        changed["candidate"]["contentDigest"] = validator.canonical_digest(
            changed["candidate"]
        )
        changed["decision"]["candidateDigest"] = changed["candidate"][
            "contentDigest"
        ]
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "acquisitionCosts must be zero"
        ):
            validator.validate_semantics(changed)

    def test_scale_requires_exact_economics_binding(self):
        changed = self.confirmed_scale_bundle()
        del changed["record"]["unitEconomicsRef"]
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "unitEconomicsRef"
        ):
            validator.validate_semantics(changed)

    def test_scale_rejects_nonpositive_contribution(self):
        changed = self.confirmed_scale_bundle()
        changed["unitEconomics"]["variableCosts"] = 3200
        changed["unitEconomics"]["acquisitionCosts"] = 100
        changed["unitEconomics"]["experimentCosts"] = 0
        changed["unitEconomics"]["netContribution"] = -300
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "positive confirmed"
        ):
            validator.validate_semantics(changed)

    def test_snapshot_cannot_drop_durable_record(self):
        changed = self.confirmed_scale_bundle()
        changed["snapshot"]["sourceRecordRefs"] = []
        with self.assertRaisesRegex(
            validator.ProfitTraceValidationError, "must include record.id"
        ):
            validator.validate_semantics(changed)

    def test_full_validation_rejects_malformed_datetime(self):
        changed = copy.deepcopy(self.bundle)
        changed["economicSignal"]["observedAt"] = "not-a-date-time"
        with tempfile.TemporaryDirectory() as directory:
            bundle_path = Path(directory) / "bundle.json"
            bundle_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(
                validator.ProfitTraceValidationError,
                "JSON Schema validation failed",
            ):
                validator.validate_file(bundle_path, SCHEMA)


if __name__ == "__main__":
    unittest.main()
