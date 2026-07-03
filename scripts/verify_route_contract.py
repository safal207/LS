#!/usr/bin/env python3
"""Run the complete deterministic Route Artifact v2 contract suite."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "modules"))

from route_artifact import RouteArtifactError, compute_content_digest, verify_route_artifact  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "routes"
SCHEMA = ROOT / "schemas" / "route_artifact_v2.schema.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def materialize_t0(repo: Path, head: str) -> dict:
    artifact = copy.deepcopy(read_json(FIXTURES / "route_t0_valid.json"))
    artifact["verification"]["exact_head"] = head
    artifact["verification"]["source"] = {
        "host": "github.com",
        "repository": "example/route-fixture",
        "ref": "HEAD",
        "commit": head,
    }
    artifact["integrity"]["content_digest"] = compute_content_digest(artifact)
    return artifact


def main() -> int:
    schema = read_json(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)

    with source_checkout() as (repo, head):
        t0 = materialize_t0(repo, head)
        validator.validate(t0)
        verify_route_artifact(t0, repository_root=repo)

    t1 = read_json(FIXTURES / "route_t1_valid.json")
    validator.validate(t1)
    verify_route_artifact(t1)

    t2 = read_json(FIXTURES / "route_t2_rejected.json")
    validator.validate(t2)
    try:
        verify_route_artifact(t2)
    except RouteArtifactError as exc:
        if exc.code != "ROUTE-V2-T2":
            raise
    else:
        raise RouteArtifactError("ROUTE-V2-SUITE", "T2 fixture entered the canonical store")
    verify_route_artifact(t2, canonical_store=False)

    test_path = ROOT / "tests" / "test_route_artifact.py"
    spec = importlib.util.spec_from_file_location("test_route_artifact", test_path)
    if spec is None or spec.loader is None:
        raise RouteArtifactError("ROUTE-V2-SUITE", f"cannot load tests from {test_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if not result.wasSuccessful():
        return 1

    summary = {
        "schema": "valid",
        "t0": "source-bound-and-replayed",
        "t1": "artifact-attested",
        "t2": "rejected-canonical-audited",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
    }
    sys.stdout.write(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
