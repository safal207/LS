from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from jsonschema import Draft202012Validator

from identity_timeline_api_fixtures import build_timeline_bundle
from trusted_runtime.identity_timeline_api import (
    DirectoryIdentityTimelineRepository,
    IdentityTimelineReadOnlyAPI,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/identity_timeline_api.schema.json"


def _payload(response):
    return json.loads(response[2].decode("utf-8"))


def test_read_only_api_lists_multiple_agents_and_valid_timeline(tmp_path: Path) -> None:
    first = build_timeline_bundle(tmp_path, "agent:alpha")
    second = build_timeline_bundle(tmp_path, "agent:beta")
    api = IdentityTimelineReadOnlyAPI(DirectoryIdentityTimelineRepository(tmp_path))

    agents_response = api.handle("GET", "/api/v1/agents")
    agents = _payload(agents_response)["agents"]
    assert agents_response[0] == 200
    assert [item["agent_id"] for item in agents] == ["agent:alpha", "agent:beta"]
    assert all(item["integrity_status"] == "VALID" for item in agents)

    encoded = quote(first["agent_id"], safe="")
    timeline_response = api.handle(
        "GET",
        f"/api/v1/agents/{encoded}/timeline",
    )
    timeline = _payload(timeline_response)
    assert timeline_response[0] == 200
    assert timeline["read_only"] is True
    assert timeline["authoritative"] is True
    assert timeline["integrity_status"] == "VALID"
    assert timeline["active_profile"]["version"] == 3
    assert timeline["active_profile"]["traits"]["requires_bounded_evidence"] is False
    assert len(timeline["timeline"]["events"]) == 9
    assert all(
        item["source_record_url"].startswith("/api/v1/agents/")
        for item in timeline["timeline"]["events"]
    )

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(timeline))
    assert second["timeline"]["active_profile"]["version"] == 3


def test_profiles_expose_version_diffs_and_event_source_records(tmp_path: Path) -> None:
    fixture = build_timeline_bundle(tmp_path, "agent:profiles")
    api = IdentityTimelineReadOnlyAPI(DirectoryIdentityTimelineRepository(tmp_path))
    encoded = quote(fixture["agent_id"], safe="")

    profiles = _payload(
        api.handle("GET", f"/api/v1/agents/{encoded}/profiles")
    )["profiles"]
    assert [item["version"] for item in profiles] == [1, 2, 3]
    assert profiles[-1]["authoritative"] is True
    assert profiles[1]["trait_changes"]
    assert profiles[2]["trait_changes"]

    timeline = _payload(
        api.handle("GET", f"/api/v1/agents/{encoded}/timeline")
    )
    first_event = timeline["timeline"]["events"][0]
    event_response = api.handle("GET", first_event["source_record_url"])
    event = _payload(event_response)["event"]
    assert event_response[0] == 200
    assert event["event_ref"] == first_event["event_ref"]
    assert event["payload"]["payload"]["record"]


def test_all_mutation_methods_are_rejected_without_touching_event_store(
    tmp_path: Path,
) -> None:
    fixture = build_timeline_bundle(tmp_path, "agent:readonly")
    api = IdentityTimelineReadOnlyAPI(DirectoryIdentityTimelineRepository(tmp_path))
    encoded = quote(fixture["agent_id"], safe="")
    path = f"/api/v1/agents/{encoded}/timeline"
    before = fixture["events_path"].read_bytes()

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = api.handle(method, path)
        payload = _payload(response)
        assert response[0] == 405
        assert payload["error"] == "method_not_allowed"
        assert dict(response[3])["Allow"] == "GET, HEAD"

    for _ in range(3):
        assert api.handle("GET", path)[0] == 200
        assert api.handle("HEAD", path)[2] == b""

    assert fixture["events_path"].read_bytes() == before


def test_evidence_downloads_return_original_files(tmp_path: Path) -> None:
    fixture = build_timeline_bundle(tmp_path, "agent:evidence")
    api = IdentityTimelineReadOnlyAPI(DirectoryIdentityTimelineRepository(tmp_path))
    encoded = quote(fixture["agent_id"], safe="")

    timeline_response = api.handle(
        "GET",
        f"/api/v1/agents/{encoded}/evidence/identity-timeline.json",
    )
    events_response = api.handle(
        "GET",
        f"/api/v1/agents/{encoded}/evidence/identity-events.jsonl",
    )
    assert timeline_response[2] == fixture["timeline_path"].read_bytes()
    assert events_response[2] == fixture["events_path"].read_bytes()
    assert "attachment" in dict(timeline_response[3])["Content-Disposition"]
    assert "attachment" in dict(events_response[3])["Content-Disposition"]
