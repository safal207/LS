from __future__ import annotations

import json
from pathlib import Path

from generate_agent_context import OUTPUT_PATH, build_agent_context

ROOT = Path(__file__).resolve().parents[1]


def test_agent_context_latest_matches_generator() -> None:
    generated = build_agent_context(ROOT)
    committed = json.loads((ROOT / OUTPUT_PATH).read_text(encoding="utf-8"))

    assert committed == generated


def test_agent_context_records_route_boundaries() -> None:
    context = build_agent_context(ROOT)

    assert context["known_working_routes"][0]["route_id"] == "ls.route.grok_review.command_pr_pull_request"
    assert context["known_working_routes"][0]["confidence"] == "medium_high"
    assert "grok-review-command-bus-ack" in context["known_working_routes"][0]["observable_markers"]

    bad_route_ids = {route["route_id"] for route in context["known_bad_routes"]}
    assert "connector_issue_comment_command" in bad_route_ids
    assert "connector_push_command_branch" in bad_route_ids
    assert "pull_request_target_command_pr" in bad_route_ids

    assert "advisory memory" in context["authority_boundary"]
    assert "workflow_run:29027359506" in context["known_working_routes"][0]["evidence_refs"]
