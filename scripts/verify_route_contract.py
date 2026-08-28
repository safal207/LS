#!/usr/bin/env python3
"""Run the complete deterministic Route Artifact v2 contract suite."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "modules"))
sys.path.insert(0, str(ROOT / "tests"))

from route_artifact import (  # noqa: E402
    RouteArtifactError,
    compute_content_digest,
    load_promotion_thresholds,
    verify_route_artifact,
)
from route_test_support import (  # noqa: E402
    load_fixture,
    materialize_t0,
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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    configured_thresholds = load_promotion_thresholds()
    schema = read_json(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)

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
            configured_thresholds=configured_thresholds,
            execute_declared_replay=True,
            trusted_honeypot_ground_truth=TRUSTED_HONEYPOT_GROUND_TRUTH,
        )

    t1 = load_fixture("route_t1_valid.json")
    validator.validate(t1)
    verify_route_artifact(t1, configured_thresholds=configured_thresholds)

    t2 = load_fixture("route_t2_rejected.json")
    validator.validate(t2)
    try:
        verify_route_artifact(t2, configured_thresholds=configured_thresholds)
    except RouteArtifactError as exc:
        if exc.code != "ROUTE-V2-T2":
            raise
    else:
        raise RouteArtifactError(
            "ROUTE-V2-SUITE",
            "T2 fixture entered the canonical store",
        )
    verify_route_artifact(
        t2,
        canonical_store=False,
        configured_thresholds=configured_thresholds,
    )

    tests = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"),
        pattern="test_route_artifact.py",
    )
    result = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stderr,
    ).run(tests)
    if not result.wasSuccessful():
        return 1

    summary = {
        "schema": "valid",
        "t0": "clean-source-bound-machine-report-verified",
        "t1": "artifact-attested",
        "t2": "rejected-canonical-audited",
        "honeypot": "operator-ground-truth-and-executed-result-bound",
        "promotion_thresholds": "externally-configured-and-verified-count-bound",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
    }
    sys.stdout.write(
        json.dumps(
            summary,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
