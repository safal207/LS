from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from validate import TrailValidationError, validate_trail  # noqa: E402

FIXTURE = ROOT / "fixtures" / "robys_pr_164_wordmark.json"


class CausalPhaseTrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trail = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def assert_invalid(self, trail: dict, message: str) -> None:
        with self.assertRaisesRegex(TrailValidationError, message):
            validate_trail(trail)

    def node(self, trail: dict, node_id: str) -> dict:
        return next(node for node in trail["nodes"] if node["id"] == node_id)

    def edge(self, trail: dict, edge_id: str) -> dict:
        return next(edge for edge in trail["edges"] if edge["id"] == edge_id)

    def route(self, trail: dict, route_id: str) -> dict:
        return next(route for route in trail["routes"] if route["routeId"] == route_id)

    def test_real_pr_164_fixture_is_valid(self) -> None:
        validate_trail(self.trail)
        self.assertEqual(self.trail["decision"]["currentPhase"], "RISK_DISCOVERED")
        self.assertEqual(self.trail["decision"]["bestRouteId"], "route.plain-fallback")

    def test_fresh_binding_evidence_rejects_stale_head(self) -> None:
        trail = copy.deepcopy(self.trail)
        self.node(trail, "evidence.current-ci-green")["validFromHead"] = trail["subject"]["baseHead"]
        self.assert_invalid(trail, "fresh binding evidence evidence.current-ci-green must bind currentHead")

    def test_detector_cannot_be_root_cause(self) -> None:
        trail = copy.deepcopy(self.trail)
        trail["decision"]["rootCauseNodeId"] = "evidence.qodo-current-findings"
        self.node(trail, "evidence.qodo-current-findings")["claimRole"] = "ROOT_CAUSE"
        self.node(trail, "evidence.qodo-current-findings")["kind"] = "CAUSE"
        self.assert_invalid(trail, "node evidence.qodo-current-findings is not a detector")

    def test_root_cause_requires_binding_causal_edge(self) -> None:
        trail = copy.deepcopy(self.trail)
        self.edge(trail, "edge.root-causes-parser-risk")["binding"] = False
        self.assert_invalid(trail, "root cause requires at least one binding CAUSED edge")

    def test_invalidated_edge_must_target_stale_evidence(self) -> None:
        trail = copy.deepcopy(self.trail)
        target = self.node(trail, "evidence.pre-fallback-visual")
        target["evidenceStatus"] = "FRESH"
        target["validFromHead"] = trail["subject"]["currentHead"]
        target["validUntilHead"] = None
        self.assert_invalid(trail, "INVALIDATED edge edge.rebind-invalidates-old-visual must target stale evidence")

    def test_route_score_is_recomputed(self) -> None:
        trail = copy.deepcopy(self.trail)
        self.route(trail, "route.plain-fallback")["score"] = 12
        self.assert_invalid(trail, "route route.plain-fallback score does not match components")

    def test_regression_requires_unsatisfied_guard(self) -> None:
        trail = copy.deepcopy(self.trail)
        for guard in trail["phaseHistory"][-1]["guards"]:
            guard["satisfied"] = True
        self.assert_invalid(trail, "phase regression requires at least one unsatisfied guard")

    def test_unresolved_blockers_force_risk_discovered(self) -> None:
        trail = copy.deepcopy(self.trail)
        trail["phaseHistory"][-1]["phase"] = "STABLE"
        trail["phaseHistory"][-1]["transitionKind"] = "FORWARD"
        trail["decision"]["currentPhase"] = "STABLE"
        self.assert_invalid(trail, "unresolved blockers require RISK_DISCOVERED")

    def test_preceded_relation_cannot_claim_causation(self) -> None:
        trail = copy.deepcopy(self.trail)
        self.edge(trail, "edge.syntax-precedes-review")["binding"] = True
        self.assert_invalid(trail, "temporal edge edge.syntax-precedes-review cannot be binding causation")


if __name__ == "__main__":
    unittest.main()
