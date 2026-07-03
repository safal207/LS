"""Shared deterministic fixtures for Route Artifact v2 tests and CLI verification."""

from __future__ import annotations

import contextlib
import copy
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "routes"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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
def source_checkout() -> Iterator[tuple[Path, str]]:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        git(repo, "init", "-q")
        git(repo, "config", "user.name", "Route Fixture")
        git(repo, "config", "user.email", "route-fixture@example.invalid")
        git(
            repo,
            "remote",
            "add",
            "origin",
            "https://github.com/example/route-fixture.git",
        )
        (repo / "fixture.txt").write_text(
            "route-v2\n",
            encoding="utf-8",
        )
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


def materialize_t0(
    repo: Path,
    head: str,
    *,
    artifact: dict | None = None,
    compute_digest,
) -> dict:
    route = copy.deepcopy(
        artifact or load_fixture("route_t0_valid.json")
    )
    route["verification"]["exact_head"] = head
    route["verification"]["source"] = {
        "host": "github.com",
        "repository": "example/route-fixture",
        "ref": "HEAD",
        "commit": head,
    }
    route["integrity"]["content_digest"] = compute_digest(route)
    return route


def rehash(artifact: dict, *, compute_digest) -> dict:
    artifact["integrity"]["content_digest"] = compute_digest(artifact)
    return artifact
