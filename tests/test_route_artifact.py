from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

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


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout.strip()


@contextlib.contextmanager
def source_checkout():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        git(repo, "init", "-q")
        git(repo, "config", "user.name", "Route Fixture")
        git(repo, "config", "user.email", "route-fixture@example.invalid")
        git(repo, "remote", "add", "origin", "https://github.com/example/route-fixture.git")
        (repo / "fixture.txt").write_text("route-v2\n", encoding="utf-8")
        git(repo, "add", "fixture.txt")
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_DATE": "2026-07-03T00:00:00Z",
                "GIT_COMMITTER_DATE": "2026-07-03T00:00:00Z",
            }
        )
        git(repo, "commit", "-q", "-m", "fixture", env=env)
        yield repo, git(repo, "rev-parse", "HEAD")


def materialize_t0(repo: Path, head: str, artifact: dict | None = None) -> dict:
    route = copy.deepcopy(artifact or load("route_t0_valid.json"))
    route["verification"]["exact_head"] = head
    route["verification"]["source"] = {
        "host": "github.com",
        "repository": "example/route-fixture",
        "ref": "HEAD",
        "commit": head,
    }
    return rehash(route)


class RouteArtifactV2Tests(unittest.TestCase):
    def assert_code(self, code: str, fn, *args, **kwargs) -> RouteArtifactError:
        with self.assertRaises(RouteArtifactError) as context:
            fn(*args, **kwargs)
        self.assertEqual(code, context.exception.code)
        return context.exception

    def test_schema_is_closed_and_parseable(self):
        schema = json.loads((ROOT / "schemas" / "route_artifact_v2.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["verification"]["additionalProperties"])
        self.assertFalse(schema["properties"]["metrics"]["additionalProperties"])

    def test_schema_and_verifier_accept_t0_t1_t2_modes(self):
        schema = json.loads((ROOT / "schemas" / "route_artifact_v2.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        with source_checkout() as (repo, head):
            t0 = materialize_t0(repo, head)
            validator.validate(t0)
            verify_route_artifact(t0, repository_root=repo)
        t1 = load("route_t1_valid.json")
        validator.validate(t1)
        verify_route_artifact(t1)
        t2 = load("route_t2_rejected.json")
        validator.validate(t2)
        verify_route_artifact(t2, canonical_store=False)

    def test_schema_and_verifier_reject_unknown_verification_field(self):
        schema = json.loads((ROOT / "schemas" / "route_artifact_v2.schema.json").read_text(encoding="utf-8"))
        artifact = load("route_t1_valid.json")
        artifact["verification"]["trust_me"] = True
        rehash(artifact)
        self.assertTrue(list(jsonschema.Draft202012Validator(schema).iter_errors(artifact)))
        self.assert_code("ROUTE-V2-SHAPE", verify_route_artifact, artifact)

    def test_cli_rejects_t2_audit_flag_in_registry_mode(self):
        cli_path = ROOT / "scripts" / "verify_route_artifact.py"
        spec = importlib.util.spec_from_file_location("verify_route_artifact_cli", cli_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as context:
                module.main(
                    [
                        "--registry",
                        str(FIXTURES / "route_t1_valid.json"),
                        "--allow-t2-audit",
                    ]
                )
        self.assertEqual(2, context.exception.code)

    def test_schema_rejects_non_t0_confirmed_metric(self):
        schema = json.loads((ROOT / "schemas" / "route_artifact_v2.schema.json").read_text(encoding="utf-8"))
        artifact = load("route_t1_valid.json")
        artifact["metrics"]["false_positive_rate"] = {
            "point": 0.2,
            "ci95": {"lower": 0.1, "upper": 0.3},
        }
        rehash(artifact)
        self.assertTrue(list(jsonschema.Draft202012Validator(schema).iter_errors(artifact)))
        self.assert_code("ROUTE-V2-METRIC", verify_route_artifact, artifact)

    def test_t0_is_canonical_training_eligible_and_source_bound(self):
        with source_checkout() as (repo, head):
            result = verify_route_artifact(materialize_t0(repo, head), repository_root=repo)
        self.assertEqual("T0_deterministic_replay", result["tier"])
        self.assertTrue(result["canonical_store_eligible"])
        self.assertTrue(result["training_eligible"])
        self.assertTrue(result["source_bound"])

    def test_t0_requires_repository_checkout(self):
        self.assert_code("ROUTE-V2-HEAD", verify_route_artifact, load("route_t0_valid.json"))

    def test_t0_rejects_wrong_checkout_head(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(repo, "1" * 40)
            self.assertNotEqual(head, artifact["verification"]["exact_head"])
            self.assert_code("ROUTE-V2-HEAD", verify_route_artifact, artifact, repository_root=repo)

    def test_t0_rejects_wrong_origin_repository(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(repo, head)
            artifact["verification"]["source"]["repository"] = "example/other"
            rehash(artifact)
            self.assert_code("ROUTE-V2-HEAD", verify_route_artifact, artifact, repository_root=repo)

    def test_t0_rejects_source_commit_mismatch(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(repo, head)
            artifact["verification"]["source"]["commit"] = "1" * 40
            rehash(artifact)
            self.assert_code("ROUTE-V2-HEAD", verify_route_artifact, artifact, repository_root=repo)

    def test_t1_is_stored_but_not_confirmed_or_training_eligible(self):
        result = verify_route_artifact(load("route_t1_valid.json"))
        self.assertEqual("T1_artifact_attested", result["tier"])
        self.assertTrue(result["canonical_store_eligible"])
        self.assertFalse(result["training_eligible"])
        self.assertFalse(result["source_bound"])

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
        artifact = load("route_t1_valid.json")
        artifact["task_profile"]["risk_level"] = "critical"
        self.assert_code("ROUTE-V2-DIGEST", verify_route_artifact, artifact)

    def test_unicode_normalization_produces_same_digest(self):
        composed = load("route_t1_valid.json")
        decomposed = copy.deepcopy(composed)
        composed["provenance"]["contributors"] = ["Café"]
        decomposed["provenance"]["contributors"] = ["Cafe\u0301"]
        self.assertEqual(compute_content_digest(composed), compute_content_digest(decomposed))

    def test_non_finite_number_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["metrics"]["reviewer_minutes_saved"]["point"] = math.inf
        self.assert_code("ROUTE-V2-CANONICAL", compute_content_digest, artifact)

    def test_non_sha256_digest_algorithm_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["integrity"]["digest_algorithm"] = "sha1"
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

    def test_duplicate_replay_assertions_are_rejected(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["replay"]["assertions"].append(
            copy.deepcopy(artifact["verification"]["replay"]["assertions"][0])
        )
        rehash(artifact)
        self.assert_code("ROUTE-V2-REPLAY", verify_route_artifact, artifact)

    def test_t1_cannot_enter_training_corpus(self):
        artifact = load("route_t1_valid.json")
        artifact["training"] = {"eligible": True, "corpus_scope": "research"}
        artifact["license"]["training_permission"] = "open_weight_only_v1"
        rehash(artifact)
        self.assert_code("ROUTE-V2-TRAINING", verify_route_artifact, artifact)

    def test_t1_cannot_claim_any_confirmed_metric(self):
        for key in ("confirmed_effectiveness", "false_positive_rate", "reviewer_minutes_saved"):
            artifact = load("route_t1_valid.json")
            artifact["metrics"][key] = {"point": 0.5, "ci95": {"lower": 0.1, "upper": 0.9}}
            rehash(artifact)
            with self.subTest(key=key):
                self.assert_code("ROUTE-V2-METRIC", verify_route_artifact, artifact)

    def test_t1_requires_artifact_refs(self):
        artifact = load("route_t1_valid.json")
        artifact["verification"]["artifact_refs"] = []
        rehash(artifact)
        self.assert_code("ROUTE-V2-T1", verify_route_artifact, artifact)

    def test_t1_requires_human_sign_off(self):
        artifact = load("route_t1_valid.json")
        artifact["verification"]["human_sign_off"] = None
        rehash(artifact)
        self.assert_code("ROUTE-V2-T1", verify_route_artifact, artifact)

    def test_t1_cannot_claim_verified_source(self):
        artifact = load("route_t1_valid.json")
        artifact["verification"]["source"] = {
            "host": "github.com",
            "repository": "example/route-fixture",
            "ref": "HEAD",
            "commit": "1" * 40,
        }
        rehash(artifact)
        self.assert_code("ROUTE-V2-T1", verify_route_artifact, artifact)

    def test_unhashable_stage_dependency_fails_with_stable_code(self):
        artifact = load("route_t1_valid.json")
        artifact["stages"][2]["depends_on"].append(["not", "hashable"])
        rehash(artifact)
        self.assert_code("ROUTE-V2-STAGE", verify_route_artifact, artifact)

    def test_missing_stage_dependency_fails_closed(self):
        artifact = load("route_t1_valid.json")
        artifact["stages"][2]["depends_on"].append("missing_stage")
        rehash(artifact)
        self.assert_code("ROUTE-V2-STAGE", verify_route_artifact, artifact)

    def test_non_prior_dependency_rejects_cycle_shape(self):
        artifact = load("route_t1_valid.json")
        artifact["stages"][0]["depends_on"] = ["regression_scan"]
        rehash(artifact)
        self.assert_code("ROUTE-V2-STAGE", verify_route_artifact, artifact)

    def test_self_supersession_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["lineage"]["supersedes"] = ["high-risk-code-review@2.0.0"]
        rehash(artifact)
        self.assert_code("ROUTE-V2-LINEAGE", verify_route_artifact, artifact)

    def test_duplicate_supersession_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["lineage"]["supersedes"] = [
            "high-risk-code-review@1.0.0",
            "high-risk-code-review@1.0.0",
        ]
        rehash(artifact)
        self.assert_code("ROUTE-V2-LINEAGE", verify_route_artifact, artifact)

    def test_non_t0_candidate_is_rejected_explicitly(self):
        artifact = load("route_t1_valid.json")
        artifact["status"] = "candidate"
        rehash(artifact)
        self.assert_code("ROUTE-V2-PROMOTION", verify_route_artifact, artifact)

    def test_candidate_promotion_is_blocked_below_minimum_t0_runs(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(repo, head)
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
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
            )

    def test_validated_route_requires_maintainer_approval(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(repo, head)
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
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
            )

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
        self.assertEqual(
            ["high-risk-code-review@1.0.0", "high-risk-code-review@2.0.0"],
            projection["topological_order"],
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

    def test_registry_handles_deep_acyclic_lineage_iteratively(self):
        artifacts = []
        for index in range(1100):
            artifact = load("route_t1_valid.json")
            artifact["route_id"] = f"route-{index}"
            artifact["version"] = "1.0.0"
            artifact["lineage"] = (
                {"supersedes": []}
                if index == 0
                else {"supersedes": [f"route-{index - 1}@1.0.0"]}
            )
            rehash(artifact)
            artifacts.append(artifact)
        projection = build_registry_projection(artifacts)
        self.assertEqual(1100, len(projection["topological_order"]))

    def test_immutable_version_cannot_be_rewritten(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(repo, head)
            existing = {"high-risk-code-review@2.0.0": artifact["integrity"]["content_digest"]}
            mutated = copy.deepcopy(artifact)
            mutated["task_profile"]["risk_level"] = "critical"
            rehash(mutated)
            self.assert_code(
                "ROUTE-V2-IMMUTABLE",
                verify_immutable_update,
                existing,
                mutated,
                repository_root=repo,
            )


if __name__ == "__main__":
    unittest.main()
