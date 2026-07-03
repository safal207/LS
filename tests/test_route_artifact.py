from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "modules"))

from route_artifact import (  # noqa: E402
    RouteArtifactError,
    build_registry_projection,
    compute_content_digest,
    verify_immutable_update,
    verify_route_artifact,
)

FIXTURES = ROOT / "tests" / "fixtures" / "routes"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def rehash(artifact: dict) -> dict:
    artifact["integrity"]["content_digest"] = compute_content_digest(artifact)
    return artifact


class RouteArtifactV2Tests(unittest.TestCase):
    def assert_code(self, code: str, fn, *args, **kwargs) -> RouteArtifactError:
        with self.assertRaises(RouteArtifactError) as context:
            fn(*args, **kwargs)
        self.assertEqual(code, context.exception.code)
        return context.exception

    def test_schema_is_closed_and_parseable(self):
        schema = json.loads((ROOT / "schemas" / "route_artifact_v2.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["verification"]["additionalProperties"])
        self.assertFalse(schema["properties"]["metrics"]["additionalProperties"])

    def test_t0_is_canonical_and_training_eligible(self):
        result = verify_route_artifact(load("route_t0_valid.json"))
        self.assertEqual("T0_deterministic_replay", result["tier"])
        self.assertTrue(result["canonical_store_eligible"])
        self.assertTrue(result["training_eligible"])

    def test_t1_is_stored_but_not_confirmed_or_training_eligible(self):
        result = verify_route_artifact(load("route_t1_valid.json"))
        self.assertEqual("T1_artifact_attested", result["tier"])
        self.assertTrue(result["canonical_store_eligible"])
        self.assertFalse(result["training_eligible"])

    def test_t2_is_rejected_from_canonical_store(self):
        artifact = load("route_t2_rejected.json")
        self.assert_code("ROUTE-V2-T2", verify_route_artifact, artifact)
        audit = verify_route_artifact(artifact, canonical_store=False)
        self.assertFalse(audit["canonical_store_eligible"])

    def test_t2_audit_requires_narrative(self):
        artifact = load("route_t2_rejected.json")
        artifact["verification"]["narrative"] = None
        rehash(artifact)
        self.assert_code("ROUTE-V2-T2", verify_route_artifact, artifact, canonical_store=False)

    def test_digest_detects_protected_byte_change(self):
        artifact = load("route_t0_valid.json")
        artifact["task_profile"]["risk_level"] = "critical"
        self.assert_code("ROUTE-V2-DIGEST", verify_route_artifact, artifact)

    def test_t0_requires_exact_head(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["exact_head"] = None
        rehash(artifact)
        self.assert_code("ROUTE-V2-T0", verify_route_artifact, artifact)

    def test_t0_requires_successful_replay(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["replay"]["observed_exit_code"] = 1
        artifact["verification"]["replay"]["passed"] = False
        rehash(artifact)
        self.assert_code("ROUTE-V2-REPLAY", verify_route_artifact, artifact)

    def test_t1_cannot_enter_training_corpus(self):
        artifact = load("route_t1_valid.json")
        artifact["training"] = {"eligible": True, "corpus_scope": "research"}
        artifact["license"]["training_permission"] = "open_weight_only_v1"
        rehash(artifact)
        self.assert_code("ROUTE-V2-TRAINING", verify_route_artifact, artifact)

    def test_t1_cannot_claim_confirmed_effectiveness(self):
        artifact = load("route_t1_valid.json")
        artifact["metrics"]["confirmed_effectiveness"] = {
            "point": 0.8,
            "ci95": {"lower": 0.4, "upper": 0.95},
        }
        rehash(artifact)
        self.assert_code("ROUTE-V2-METRIC", verify_route_artifact, artifact)

    def test_unknown_field_fails_closed(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["trust_me"] = True
        rehash(artifact)
        self.assert_code("ROUTE-V2-SHAPE", verify_route_artifact, artifact)

    def test_missing_stage_dependency_fails_closed(self):
        artifact = load("route_t0_valid.json")
        artifact["stages"][2]["depends_on"].append("missing_stage")
        rehash(artifact)
        self.assert_code("ROUTE-V2-STAGE", verify_route_artifact, artifact)

    def test_non_prior_dependency_rejects_cycle_shape(self):
        artifact = load("route_t0_valid.json")
        artifact["stages"][0]["depends_on"] = ["regression_scan"]
        rehash(artifact)
        self.assert_code("ROUTE-V2-STAGE", verify_route_artifact, artifact)

    def test_candidate_promotion_is_blocked_below_minimum_t0_runs(self):
        artifact = load("route_t0_valid.json")
        artifact["status"] = "candidate"
        artifact["metrics"]["confirmed_effectiveness"] = {
            "point": 0.7,
            "ci95": {"lower": 0.4, "upper": 0.9},
        }
        artifact["metrics"]["false_positive_rate"] = {
            "point": 0.1,
            "ci95": {"lower": 0.0, "upper": 0.3},
        }
        rehash(artifact)
        self.assert_code("ROUTE-V2-PROMOTION", verify_route_artifact, artifact)

    def test_validated_route_requires_maintainer_approval(self):
        artifact = load("route_t0_valid.json")
        artifact["status"] = "validated"
        artifact["metrics"].update(
            {
                "sample_size": 20,
                "t0_runs": 20,
                "repository_count": 2,
                "task_variant_count": 2,
                "sealed_honeypot_runs": 1,
                "unresolved_critical_false_negatives": 0,
                "confirmed_effectiveness": {
                    "point": 0.75,
                    "ci95": {"lower": 0.55, "upper": 0.88},
                },
                "false_positive_rate": {
                    "point": 0.08,
                    "ci95": {"lower": 0.01, "upper": 0.2},
                },
                "maintainer_approved": False,
            }
        )
        rehash(artifact)
        self.assert_code("ROUTE-V2-PROMOTION", verify_route_artifact, artifact)

    def test_registry_derives_reverse_superseded_by_edge(self):
        v1 = load("route_t1_valid.json")
        v1["version"] = "1.0.0"
        v1["lineage"] = {"supersedes": []}
        rehash(v1)
        v2 = load("route_t1_valid.json")
        v2["version"] = "2.0.0"
        v2["lineage"] = {"supersedes": ["high-risk-code-review@1.0.0"]}
        rehash(v2)
        projection = build_registry_projection([v1, v2])
        by_ref = {item["route_ref"]: item for item in projection["routes"]}
        self.assertEqual(
            ["high-risk-code-review@2.0.0"],
            by_ref["high-risk-code-review@1.0.0"]["superseded_by"],
        )
        self.assertEqual(
            ["high-risk-code-review@1.0.0"],
            by_ref["high-risk-code-review@2.0.0"]["supersedes"],
        )

    def test_registry_rejects_missing_supersession_target(self):
        v2 = load("route_t1_valid.json")
        v2["lineage"] = {"supersedes": ["high-risk-code-review@1.0.0"]}
        rehash(v2)
        self.assert_code("ROUTE-V2-REGISTRY", build_registry_projection, [v2])

    def test_registry_rejects_multi_hop_cycle(self):
        v1 = load("route_t1_valid.json")
        v1["version"] = "1.0.0"
        v1["lineage"] = {"supersedes": ["high-risk-code-review@2.0.0"]}
        rehash(v1)
        v2 = load("route_t1_valid.json")
        v2["version"] = "2.0.0"
        v2["lineage"] = {"supersedes": ["high-risk-code-review@1.0.0"]}
        rehash(v2)
        self.assert_code("ROUTE-V2-REGISTRY", build_registry_projection, [v1, v2])

    def test_immutable_version_cannot_be_rewritten(self):
        artifact = load("route_t0_valid.json")
        existing = {"high-risk-code-review@2.0.0": artifact["integrity"]["content_digest"]}
        mutated = copy.deepcopy(artifact)
        mutated["task_profile"]["risk_level"] = "critical"
        rehash(mutated)
        self.assert_code("ROUTE-V2-IMMUTABLE", verify_immutable_update, existing, mutated)


if __name__ == "__main__":
    unittest.main()
