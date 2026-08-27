from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "modules"))
sys.path.insert(0, str(ROOT / "tests"))

from route_artifact import (  # noqa: E402
    RouteArtifactError,
    build_registry_projection,
    compute_content_digest,
    compute_replay_evidence_digest,
    verify_immutable_update,
    verify_route_artifact,
)
from route_test_support import (  # noqa: E402
    FIXTURES,
    git,
    load_fixture,
    materialize_t0,
    rehash,
    source_checkout,
)

SCHEMA = ROOT / "schemas" / "route_artifact_v2.schema.json"
TRUSTED_HONEYPOT_GROUND_TRUTH = {
    "high-risk-code-review@2.0.0": {
        "terminal_authority_multihop": (
            "87a1cff9555e6cca337bf0e13fc64e60"
            "a493cb26b3a1c4e36c2deec00cc2c5c1"
        )
    }
}
_verify_route_artifact = verify_route_artifact


def verify_route_artifact(*args, **kwargs):
    if kwargs.get("execute_declared_replay"):
        kwargs.setdefault(
            "trusted_honeypot_ground_truth",
            TRUSTED_HONEYPOT_GROUND_TRUTH,
        )
    return _verify_route_artifact(*args, **kwargs)


def load(name: str) -> dict:
    return load_fixture(name)


def digest(artifact: dict) -> dict:
    return rehash(
        artifact,
        compute_digest=compute_content_digest,
    )


def make_promotable(
    repo: Path,
    head: str,
    *,
    status: str = "candidate",
) -> dict:
    artifact = materialize_t0(
        repo,
        head,
        compute_digest=compute_content_digest,
    )
    artifact["status"] = status
    artifact["metrics"].update(
        {
            "sample_size": 20,
            "t0_runs": 20,
            "repository_count": 2,
            "task_variant_count": 2,
            "sealed_honeypot_runs": 1,
            "unresolved_critical_false_negatives": 0,
            "maintainer_approved": status == "validated",
        }
    )
    return digest(artifact)


class RouteArtifactV2Tests(unittest.TestCase):
    def assert_code(
        self,
        code: str,
        fn,
        *args,
        **kwargs,
    ) -> RouteArtifactError:
        with self.assertRaises(RouteArtifactError) as context:
            fn(*args, **kwargs)
        self.assertEqual(code, context.exception.code)
        return context.exception

    def validator(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        return jsonschema.Draft202012Validator(schema)

    def test_schema_is_closed_and_parseable(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(
            schema["$defs"]["verification"]["additionalProperties"]
        )
        self.assertFalse(
            schema["$defs"]["metrics"]["additionalProperties"]
        )

    def test_schema_and_verifier_accept_all_three_tiers(self):
        validator = self.validator()
        with source_checkout() as (repo, head):
            t0 = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            validator.validate(t0)
            verify_route_artifact(
                t0,
                repository_root=repo,
                execute_declared_replay=True,
            )
        for name, canonical in (
            ("route_t1_valid.json", True),
            ("route_t2_rejected.json", False),
        ):
            artifact = load(name)
            validator.validate(artifact)
            verify_route_artifact(
                artifact,
                canonical_store=canonical,
            )

    def test_schema_and_verifier_reject_unknown_field(self):
        artifact = load("route_t1_valid.json")
        artifact["verification"]["trust_me"] = True
        digest(artifact)
        self.assertTrue(
            list(self.validator().iter_errors(artifact))
        )
        self.assert_code(
            "ROUTE-V2-SHAPE",
            verify_route_artifact,
            artifact,
        )

    def test_cli_rejects_t2_audit_in_registry_mode(self):
        cli_path = ROOT / "scripts" / "verify_route_artifact.py"
        spec = importlib.util.spec_from_file_location(
            "verify_route_artifact_cli",
            cli_path,
        )
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

    def test_cli_rejects_duplicate_json_object_keys(self):
        cli_path = ROOT / "scripts" / "verify_route_artifact.py"
        spec = importlib.util.spec_from_file_location(
            "verify_route_artifact_duplicate_keys_cli",
            cli_path,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        source = (FIXTURES / "route_t1_valid.json").read_text(encoding="utf-8")
        source = source.replace(
            '"status": "experimental"',
            '"status": "validated",\n  "status": "experimental"',
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            artifact_path = Path(directory) / "duplicate-status.json"
            artifact_path.write_text(source, encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = module.main(["--artifact", str(artifact_path)])

        self.assertEqual(1, result)
        self.assertIn("duplicate JSON object key: status", stderr.getvalue())

    def test_t0_is_source_bound_and_training_eligible(self):
        with source_checkout() as (repo, head):
            result = verify_route_artifact(
                materialize_t0(
                    repo,
                    head,
                    compute_digest=compute_content_digest,
                ),
                repository_root=repo,
                execute_declared_replay=True,
            )
        self.assertTrue(result["canonical_store_eligible"])
        self.assertTrue(result["training_eligible"])
        self.assertTrue(result["source_bound"])
        self.assertEqual(1, result["honeypot_evaluations"])
        self.assertEqual(
            {
                "t0_runs": 1,
                "repository_count": 1,
                "task_variant_count": 1,
                "sealed_honeypot_runs": 1,
            },
            result["verified_promotion_counts"],
        )

    def test_t0_requires_explicit_operator_replay_execution(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            self.assert_code(
                "ROUTE-V2-REPLAY",
                verify_route_artifact,
                artifact,
                repository_root=repo,
            )

    def test_t0_rejects_a_declared_command_that_did_not_execute(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            replay = artifact["verification"]["replay"]
            replay["command"] = "missing-route-replay-command"
            replay["evidence_digest"] = compute_replay_evidence_digest(
                replay
            )
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-REPLAY",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_rejects_noop_with_self_declared_passing_assertions(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            replay = artifact["verification"]["replay"]
            replay["command"] = "python3 -c pass"
            replay["evidence_digest"] = compute_replay_evidence_digest(replay)
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-REPLAY",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_rejects_dirty_tracked_or_untracked_checkout(self):
        for dirty_path in ("fixture.txt", "untracked.py"):
            with self.subTest(path=dirty_path):
                with source_checkout() as (repo, head):
                    artifact = materialize_t0(
                        repo,
                        head,
                        compute_digest=compute_content_digest,
                    )
                    (repo / dirty_path).write_text(
                        "mutable replay input\n",
                        encoding="utf-8",
                    )
                    self.assert_code(
                        "ROUTE-V2-HEAD",
                        verify_route_artifact,
                        artifact,
                        repository_root=repo,
                        execute_declared_replay=True,
                    )

    def test_t0_rejects_ignored_checkout_content(self):
        with source_checkout() as (repo, _head):
            (repo / ".gitignore").write_text(
                "ignored-replay-input.json\n",
                encoding="utf-8",
            )
            git(repo, "add", ".gitignore")
            git(repo, "commit", "-q", "-m", "ignore local replay input")
            head = git(repo, "rev-parse", "HEAD")
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            (repo / "ignored-replay-input.json").write_text(
                '{"mutable":true}\n',
                encoding="utf-8",
            )

            self.assert_code(
                "ROUTE-V2-HEAD",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_rejects_git_replacement_objects(self):
        with source_checkout() as (repo, exact_head):
            artifact = materialize_t0(
                repo,
                exact_head,
                compute_digest=compute_content_digest,
            )
            (repo / "replacement-only.txt").write_text(
                "replacement tree\n",
                encoding="utf-8",
            )
            git(repo, "add", "replacement-only.txt")
            git(repo, "commit", "-q", "-m", "replacement tree")
            replacement = git(repo, "rev-parse", "HEAD")
            git(repo, "reset", "--hard", exact_head)
            git(repo, "replace", exact_head, replacement)
            git(repo, "reset", "--hard", exact_head)

            self.assertEqual(exact_head, git(repo, "rev-parse", "HEAD"))
            self.assertEqual("", git(repo, "status", "--porcelain=v1"))
            self.assertEqual(
                "replacement tree",
                git(repo, "show", "HEAD:replacement-only.txt"),
            )
            self.assert_code(
                "ROUTE-V2-HEAD",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_rejects_self_declared_honeypot_without_operator_truth(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            self.assert_code(
                "ROUTE-V2-HONEYPOT",
                _verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_binds_honeypot_result_to_executed_output(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            artifact["verification"]["honeypot_evaluations"][0][
                "observed_result_digest"
            ] = "0" * 64
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-HONEYPOT",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_hashes_actual_honeypot_result_in_the_verifier(self):
        with source_checkout() as (repo, _head):
            replay_script = repo / "scripts" / "verify_route_contract.py"
            disclosed_commitment = TRUSTED_HONEYPOT_GROUND_TRUTH[
                "high-risk-code-review@2.0.0"
            ]["terminal_authority_multihop"]
            replay_script.write_text(
                (
                    "import json\n"
                    "print(json.dumps({\n"
                    "    'assertions': [\n"
                    "        {'name': 'fixture file content is exact', 'passed': True},\n"
                    "        {'name': 'replay script is source-bound', 'passed': True},\n"
                    "    ],\n"
                    "    'honeypot_results': {\n"
                    "        'terminal_authority_multihop': "
                    f"{disclosed_commitment!r},\n"
                    "    },\n"
                    "}, sort_keys=True, separators=(',', ':')))\n"
                ),
                encoding="utf-8",
            )
            git(repo, "add", "scripts/verify_route_contract.py")
            git(repo, "commit", "-q", "-m", "echo disclosed commitment")
            head = git(repo, "rev-parse", "HEAD")
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )

            self.assert_code(
                "ROUTE-V2-HONEYPOT",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_confirmed_metrics_require_independent_scorer_evidence(self):
        cases = {
            "confirmed_effectiveness": {
                "point": 0.75,
                "ci95": {"lower": 0.55, "upper": 0.88},
            },
            "false_positive_rate": {
                "point": 0.08,
                "ci95": {"lower": 0.01, "upper": 0.2},
            },
            "reviewer_minutes_saved": {
                "point": 25.0,
                "ci95": {"lower": 10.0, "upper": 40.0},
            },
        }
        for metric_name, metric_value in cases.items():
            with self.subTest(metric=metric_name):
                with source_checkout() as (repo, head):
                    artifact = materialize_t0(
                        repo,
                        head,
                        compute_digest=compute_content_digest,
                    )
                    artifact["metrics"][metric_name] = metric_value
                    digest(artifact)

                    self.assertTrue(list(self.validator().iter_errors(artifact)))
                    self.assert_code(
                        "ROUTE-V2-METRIC",
                        verify_route_artifact,
                        artifact,
                        repository_root=repo,
                        execute_declared_replay=True,
                    )

    def test_t0_requires_repository_checkout(self):
        self.assert_code(
            "ROUTE-V2-HEAD",
            verify_route_artifact,
            load("route_t0_valid.json"),
        )

    def test_t0_rejects_wrong_checkout_head(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                "1" * 40,
                compute_digest=compute_content_digest,
            )
            self.assertNotEqual(
                head,
                artifact["verification"]["exact_head"],
            )
            self.assert_code(
                "ROUTE-V2-HEAD",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_rejects_wrong_origin_repository(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            artifact["verification"]["source"][
                "repository"
            ] = "example/other"
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-HEAD",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_rejects_source_commit_mismatch(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            artifact["verification"]["source"][
                "commit"
            ] = "1" * 40
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-HEAD",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t0_requires_successful_replay(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["replay"][
            "observed_exit_code"
        ] = 1
        artifact["verification"]["replay"]["passed"] = False
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-REPLAY",
            verify_route_artifact,
            artifact,
        )

    def test_t0_rejects_duplicate_replay_assertion(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["replay"]["assertions"].append(
            copy.deepcopy(
                artifact["verification"]["replay"]["assertions"][0]
            )
        )
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-REPLAY",
            verify_route_artifact,
            artifact,
        )

    def test_replay_evidence_digest_detects_post_digest_mutation(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["replay"][
            "command"
        ] = "python3 altered_replay.py"
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-DIGEST",
            verify_route_artifact,
            artifact,
        )

    def test_honeypot_requires_sealed_true(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["honeypot_evaluations"][0][
            "sealed"
        ] = False
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-HONEYPOT",
            verify_route_artifact,
            artifact,
        )

    def test_honeypot_requires_ground_truth_match(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["honeypot_evaluations"][0][
            "matched"
        ] = False
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-HONEYPOT",
            verify_route_artifact,
            artifact,
        )

    def test_honeypot_requires_sha256_digests(self):
        artifact = load("route_t0_valid.json")
        artifact["verification"]["honeypot_evaluations"][0][
            "ground_truth_digest"
        ] = "bad"
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-HONEYPOT",
            verify_route_artifact,
            artifact,
        )

    def test_honeypot_count_must_equal_evidence_count(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            artifact["metrics"]["sealed_honeypot_runs"] = 2
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-HONEYPOT",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_t1_is_stored_but_not_confirmed(self):
        result = verify_route_artifact(
            load("route_t1_valid.json")
        )
        self.assertTrue(result["canonical_store_eligible"])
        self.assertFalse(result["training_eligible"])
        self.assertFalse(result["source_bound"])

    def test_t1_requires_artifact_refs(self):
        artifact = load("route_t1_valid.json")
        artifact["verification"]["artifact_refs"] = []
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-T1",
            verify_route_artifact,
            artifact,
        )

    def test_t1_requires_human_signoff(self):
        artifact = load("route_t1_valid.json")
        artifact["verification"]["human_sign_off"] = None
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-T1",
            verify_route_artifact,
            artifact,
        )

    def test_t1_rejects_honeypot_claim(self):
        artifact = load("route_t1_valid.json")
        artifact["verification"]["honeypot_evaluations"] = [
            copy.deepcopy(
                load("route_t0_valid.json")[
                    "verification"
                ]["honeypot_evaluations"][0]
            )
        ]
        artifact["metrics"]["sealed_honeypot_runs"] = 1
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-T1",
            verify_route_artifact,
            artifact,
        )

    def test_non_t0_cannot_claim_any_confirmed_metric(self):
        for key in (
            "confirmed_effectiveness",
            "false_positive_rate",
            "reviewer_minutes_saved",
        ):
            artifact = load("route_t1_valid.json")
            artifact["metrics"][key] = {
                "point": 0.5,
                "ci95": {"lower": 0.1, "upper": 0.9},
            }
            digest(artifact)
            with self.subTest(key=key):
                self.assert_code(
                    "ROUTE-V2-METRIC",
                    verify_route_artifact,
                    artifact,
                )

    def test_non_t0_cannot_enter_training(self):
        artifact = load("route_t1_valid.json")
        artifact["training"] = {
            "eligible": True,
            "corpus_scope": "research",
        }
        artifact["license"][
            "training_permission"
        ] = "open_weight_only_v1"
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-TRAINING",
            verify_route_artifact,
            artifact,
        )

    def test_t2_rejected_from_canonical_store(self):
        artifact = load("route_t2_rejected.json")
        self.assert_code(
            "ROUTE-V2-T2",
            verify_route_artifact,
            artifact,
        )
        result = verify_route_artifact(
            artifact,
            canonical_store=False,
        )
        self.assertFalse(result["canonical_store_eligible"])

    def test_t2_audit_requires_narrative(self):
        artifact = load("route_t2_rejected.json")
        artifact["verification"]["narrative"] = None
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-T2",
            verify_route_artifact,
            artifact,
            canonical_store=False,
        )

    def test_t2_audit_rejects_artifact_refs(self):
        artifact = load("route_t2_rejected.json")
        artifact["verification"]["artifact_refs"] = ["x"]
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-T2",
            verify_route_artifact,
            artifact,
            canonical_store=False,
        )

    def test_t2_audit_rejects_human_signoff(self):
        artifact = load("route_t2_rejected.json")
        artifact["verification"]["human_sign_off"] = {
            "actor": "human",
            "signed_at": "2026-07-03T00:00:00Z",
            "decision": "attested",
        }
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-T2",
            verify_route_artifact,
            artifact,
            canonical_store=False,
        )

    def test_t2_audit_rejects_exact_head(self):
        artifact = load("route_t2_rejected.json")
        artifact["verification"]["exact_head"] = "1" * 40
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-T2",
            verify_route_artifact,
            artifact,
            canonical_store=False,
        )

    def test_digest_detects_protected_change(self):
        artifact = load("route_t1_valid.json")
        artifact["task_profile"]["risk_level"] = "critical"
        self.assert_code(
            "ROUTE-V2-DIGEST",
            verify_route_artifact,
            artifact,
        )

    def test_unicode_normalization_produces_same_digest(self):
        composed = load("route_t1_valid.json")
        decomposed = copy.deepcopy(composed)
        composed["provenance"]["contributors"] = ["Café"]
        decomposed["provenance"]["contributors"] = [
            "Cafe\u0301"
        ]
        self.assertEqual(
            compute_content_digest(composed),
            compute_content_digest(decomposed),
        )

    def test_non_finite_number_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["metrics"]["reviewer_minutes_saved"][
            "point"
        ] = math.inf
        self.assert_code(
            "ROUTE-V2-CANONICAL",
            compute_content_digest,
            artifact,
        )

    def test_non_sha256_algorithm_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["integrity"]["digest_algorithm"] = "sha1"
        self.assert_code(
            "ROUTE-V2-DIGEST",
            verify_route_artifact,
            artifact,
        )

    def test_unhashable_dependency_fails_stably(self):
        artifact = load("route_t1_valid.json")
        artifact["stages"][2]["depends_on"].append(
            ["not", "hashable"]
        )
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-STAGE",
            verify_route_artifact,
            artifact,
        )

    def test_missing_stage_dependency_fails(self):
        artifact = load("route_t1_valid.json")
        artifact["stages"][2]["depends_on"].append(
            "missing_stage"
        )
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-STAGE",
            verify_route_artifact,
            artifact,
        )

    def test_non_prior_dependency_rejects_cycle_shape(self):
        artifact = load("route_t1_valid.json")
        artifact["stages"][0]["depends_on"] = [
            "regression_scan"
        ]
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-STAGE",
            verify_route_artifact,
            artifact,
        )

    def test_self_supersession_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["lineage"]["supersedes"] = [
            "high-risk-code-review@2.0.0"
        ]
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-LINEAGE",
            verify_route_artifact,
            artifact,
        )

    def test_duplicate_supersession_is_rejected(self):
        artifact = load("route_t1_valid.json")
        artifact["lineage"]["supersedes"] = [
            "high-risk-code-review@1.0.0",
            "high-risk-code-review@1.0.0",
        ]
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-LINEAGE",
            verify_route_artifact,
            artifact,
        )

    def test_non_t0_candidate_rejected_explicitly(self):
        artifact = load("route_t1_valid.json")
        artifact["status"] = "candidate"
        digest(artifact)
        self.assert_code(
            "ROUTE-V2-PROMOTION",
            verify_route_artifact,
            artifact,
        )

    def test_candidate_blocked_below_minimum_t0_runs(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(repo, head)
            artifact["metrics"]["t0_runs"] = 19
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_candidate_cannot_self_lower_configured_promotion_thresholds(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(repo, head)
            artifact["promotion_policy"].update(
                {
                    "minimum_t0_runs": 1,
                    "minimum_repositories": 1,
                    "minimum_task_variants": 1,
                }
            )
            digest(artifact)
            self.assertFalse(
                list(self.validator().iter_errors(artifact))
            )
            self.assert_code(
                "ROUTE-V2-POLICY",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_external_policy_changes_threshold_without_code_change(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(repo, head)
            configured = {
                "minimum_t0_runs": 21,
                "minimum_repositories": 2,
                "minimum_task_variants": 2,
                "minimum_sealed_honeypot_runs": 1,
            }
            artifact["promotion_policy"].update(configured)
            digest(artifact)
            self.assertFalse(list(self.validator().iter_errors(artifact)))
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                configured_thresholds=configured,
                execute_declared_replay=True,
            )

            artifact["metrics"]["sample_size"] = 21
            artifact["metrics"]["t0_runs"] = 21
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                configured_thresholds=configured,
                execute_declared_replay=True,
            )

    def test_candidate_blocked_without_honeypot_evidence(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(repo, head)
            artifact["verification"][
                "honeypot_evaluations"
            ] = []
            artifact["metrics"]["sealed_honeypot_runs"] = 0
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-HONEYPOT",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_candidate_blocked_on_critical_false_negative(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(repo, head)
            artifact["metrics"][
                "unresolved_critical_false_negatives"
            ] = 1
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_candidate_blocked_without_confidence_interval(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(repo, head)
            artifact["metrics"]["false_positive_rate"] = {
                "point": None,
                "ci95": None,
            }
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_validated_rejects_producer_authored_maintainer_approval(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(
                repo,
                head,
                status="validated",
            )
            artifact["metrics"]["maintainer_approved"] = False
            digest(artifact)
            self.assert_code(
                "ROUTE-V2-GOVERNANCE",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_producer_aggregate_counts_cannot_satisfy_promotion(self):
        with source_checkout() as (repo, head):
            artifact = make_promotable(repo, head)
            self.assert_code(
                "ROUTE-V2-PROMOTION",
                verify_route_artifact,
                artifact,
                repository_root=repo,
                execute_declared_replay=True,
            )

    def test_rate_metrics_are_bounded_to_zero_one(self):
        cases = (
            ("confirmed_effectiveness", "point", 999),
            ("false_positive_rate", "point", -1),
            ("confirmed_effectiveness", "lower", -0.01),
            ("false_positive_rate", "upper", 1.01),
        )
        for metric_name, field, invalid in cases:
            with self.subTest(metric=metric_name, field=field):
                with source_checkout() as (repo, head):
                    artifact = materialize_t0(
                        repo,
                        head,
                        compute_digest=compute_content_digest,
                    )
                    metric_value = artifact["metrics"][metric_name]
                    metric_value["point"] = 0.5
                    metric_value["ci95"] = {
                        "lower": 0.25,
                        "upper": 0.75,
                    }
                    if field == "point":
                        metric_value["point"] = invalid
                        metric_value["ci95"] = {
                            "lower": min(0.0, invalid),
                            "upper": max(1.0, invalid),
                        }
                    else:
                        metric_value["ci95"][field] = invalid
                    digest(artifact)
                    self.assertTrue(
                        list(self.validator().iter_errors(artifact))
                    )
                    self.assert_code(
                        "ROUTE-V2-METRIC",
                        verify_route_artifact,
                        artifact,
                        repository_root=repo,
                        execute_declared_replay=True,
                    )

    def test_registry_derives_reverse_edge(self):
        v1 = load("route_t1_valid.json")
        v1["version"] = "1.0.0"
        v1["lineage"] = {"supersedes": []}
        digest(v1)

        v2 = load("route_t1_valid.json")
        v2["lineage"] = {
            "supersedes": [
                "high-risk-code-review@1.0.0"
            ]
        }
        digest(v2)

        projection = build_registry_projection([v1, v2])
        by_ref = {
            item["route_ref"]: item
            for item in projection["routes"]
        }
        self.assertEqual(
            ["high-risk-code-review@2.0.0"],
            by_ref[
                "high-risk-code-review@1.0.0"
            ]["superseded_by"],
        )

    def test_registry_rejects_missing_parent(self):
        v2 = load("route_t1_valid.json")
        v2["lineage"] = {
            "supersedes": [
                "high-risk-code-review@1.0.0"
            ]
        }
        digest(v2)
        self.assert_code(
            "ROUTE-V2-REGISTRY",
            build_registry_projection,
            [v2],
        )

    def test_registry_rejects_multi_hop_cycle(self):
        v1 = load("route_t1_valid.json")
        v1["version"] = "1.0.0"
        v1["lineage"] = {
            "supersedes": [
                "high-risk-code-review@2.0.0"
            ]
        }
        digest(v1)

        v2 = load("route_t1_valid.json")
        v2["lineage"] = {
            "supersedes": [
                "high-risk-code-review@1.0.0"
            ]
        }
        digest(v2)

        self.assert_code(
            "ROUTE-V2-REGISTRY",
            build_registry_projection,
            [v1, v2],
        )

    def test_registry_handles_deep_acyclic_lineage(self):
        artifacts = []
        for index in range(1100):
            artifact = load("route_t1_valid.json")
            artifact["route_id"] = f"route-{index}"
            artifact["version"] = "1.0.0"
            artifact["lineage"] = (
                {"supersedes": []}
                if index == 0
                else {
                    "supersedes": [
                        f"route-{index - 1}@1.0.0"
                    ]
                }
            )
            digest(artifact)
            artifacts.append(artifact)

        projection = build_registry_projection(artifacts)
        self.assertEqual(
            1100,
            len(projection["topological_order"]),
        )

    def test_immutable_version_cannot_be_rewritten(self):
        with source_checkout() as (repo, head):
            artifact = materialize_t0(
                repo,
                head,
                compute_digest=compute_content_digest,
            )
            existing = {
                "high-risk-code-review@2.0.0":
                    artifact["integrity"]["content_digest"]
            }
            mutated = copy.deepcopy(artifact)
            mutated["task_profile"]["risk_level"] = "critical"
            digest(mutated)
            self.assert_code(
                "ROUTE-V2-IMMUTABLE",
                verify_immutable_update,
                existing,
                mutated,
                repository_root=repo,
                execute_declared_replay=True,
                trusted_honeypot_ground_truth=(
                    TRUSTED_HONEYPOT_GROUND_TRUTH
                ),
            )


if __name__ == "__main__":
    unittest.main()
