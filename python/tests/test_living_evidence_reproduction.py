from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from multi_model_review.evidence_graph import EvidenceTier  # noqa: E402
from multi_model_review.evidence_probes import (  # noqa: E402
    load_pattern_specimen,
    run_pattern_reproductions,
)


class LivingEvidenceReproductionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "python/tests/fixtures/living_evidence_pattern_specimen/specimen.json"
        self.specimen = load_pattern_specimen(self.path)

    def test_executes_all_declared_t0_reproductions(self) -> None:
        results = run_pattern_reproductions(self.specimen)
        ids = {result.reproduction_id for result in results}
        self.assertEqual(ids, set(self.specimen["expected_reproduction_ids"]))
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result.tier == EvidenceTier.T0_REPRODUCTION for result in results))
        self.assertTrue(all(result.reproduced for result in results))

    def test_unknown_property_reproduction_covers_all_closed_object_categories(self) -> None:
        results = {result.reproduction_id: result for result in run_pattern_reproductions(self.specimen)}
        unknown = results["t0-unknown-property-parity"]
        self.assertEqual(
            set(unknown.observed),
            {"envelope", "event", "actor", "bindings"},
        )
        self.assertTrue(
            all(
                observation == {"schema_accepts": False, "runtime_accepts": True}
                for observation in unknown.observed.values()
            )
        )
        self.assertEqual(len(unknown.finding_ids), 4)

    def test_reproduction_evidence_does_not_claim_candidate_execution(self) -> None:
        results = run_pattern_reproductions(self.specimen)
        unknown = next(result for result in results if result.reproduction_id == "t0-unknown-property-parity")
        self.assertIn("candidate source was not imported", unknown.evidence)
        self.assertIn("trusted generic mutation", unknown.evidence)

    def test_loader_rejects_old_structural_only_fidelity(self) -> None:
        broken = json.loads(json.dumps(self.specimen))
        broken["artifact_fidelity"] = "SYNTHETIC_PATTERN_SPECIMEN"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "specimen.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "synthetic reproduction fidelity"):
                load_pattern_specimen(path)


if __name__ == "__main__":
    unittest.main()
