from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "modules"))
sys.path.insert(0, str(ROOT / "tests"))

from route_artifact_policy import (  # noqa: E402
    PROTOCOL_PROMOTION_FLOORS,
    RouteArtifactError,
    compute_content_digest,
    compute_replay_evidence_digest,
    verify_replay,
    verify_route_artifact,
)
from route_test_support import load_fixture, rehash  # noqa: E402


class RouteArtifactPolicyTests(unittest.TestCase):
    def assert_code(self, code: str, fn, *args, **kwargs) -> RouteArtifactError:
        with self.assertRaises(RouteArtifactError) as context:
            fn(*args, **kwargs)
        self.assertEqual(code, context.exception.code)
        return context.exception

    def test_fixture_replay_digest_matches_protected_payload(self):
        artifact = load_fixture("route_t0_valid.json")
        replay = artifact["verification"]["replay"]
        self.assertEqual(
            replay["evidence_digest"],
            compute_replay_evidence_digest(replay),
        )
        verify_replay(replay)

    def test_replay_evidence_mutation_fails_without_digest_update(self):
        artifact = load_fixture("route_t0_valid.json")
        replay = copy.deepcopy(artifact["verification"]["replay"])
        replay["assertions"][0]["name"] = "post-hoc altered evidence"
        self.assert_code("ROUTE-V2-EVIDENCE", verify_replay, replay)

    def test_replay_exit_code_mutation_fails_without_digest_update(self):
        artifact = load_fixture("route_t0_valid.json")
        replay = copy.deepcopy(artifact["verification"]["replay"])
        replay["expected_exit_code"] = 1
        replay["observed_exit_code"] = 1
        self.assert_code("ROUTE-V2-EVIDENCE", verify_replay, replay)

    def test_protocol_promotion_floors_are_fixed(self):
        self.assertEqual(
            {
                "minimum_t0_runs": 20,
                "minimum_repositories": 2,
                "minimum_task_variants": 2,
                "minimum_sealed_honeypot_runs": 1,
            },
            PROTOCOL_PROMOTION_FLOORS,
        )

    def test_artifact_cannot_override_protocol_floor(self):
        for key, expected in PROTOCOL_PROMOTION_FLOORS.items():
            artifact = load_fixture("route_t1_valid.json")
            artifact["promotion_policy"][key] = 1 if expected > 1 else 2
            rehash(artifact, compute_digest=compute_content_digest)
            with self.subTest(key=key):
                self.assert_code(
                    "ROUTE-V2-POLICY",
                    verify_route_artifact,
                    artifact,
                )


if __name__ == "__main__":
    unittest.main()
