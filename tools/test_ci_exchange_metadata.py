from __future__ import annotations

import json
from pathlib import Path

from validate_ci_exchange import AGENT_CONTEXT_PATH, REGISTRY_PATH, validate

ROOT = Path(__file__).resolve().parents[1]


def test_ci_exchange_metadata_is_consistent() -> None:
    assert validate(ROOT) == []


def test_registry_manifests_are_reachable() -> None:
    registry = json.loads((ROOT / REGISTRY_PATH).read_text(encoding="utf-8"))

    manifests = [node["manifest"] for node in registry["nodes"]]
    assert manifests

    for manifest in manifests:
        assert (ROOT / manifest).is_file()


def test_agent_context_generated_sources_exist() -> None:
    context = json.loads((ROOT / AGENT_CONTEXT_PATH).read_text(encoding="utf-8"))

    for generated_from in context["generated_from"]:
        assert (ROOT / generated_from).exists(), generated_from

    route_ids = {route["route_id"] for route in context["known_working_routes"]}
    assert "ls.route.grok_review.command_pr_pull_request" in route_ids
