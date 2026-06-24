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
from trusted_runtime.persistence import digest_json


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/identity_timeline_api.schema.json"


def _payload(response):
    return json.loads(response[2].decode("utf-8"))


def test_event_store_tampering_withholds_authoritative_profile(tmp_path: Path) -> None:
    fixture = build_timeline_bundle(tmp_path, "agent:tampered")
    lines = fixture["events_path"].read_text(encoding="utf-8").splitlines()
    changed = json.loads(lines[1])
    changed["actor"] = "attacker:changed-actor"
    lines[1] = json.dumps(changed, sort_keys=True, separators=(",", ":"))
    fixture["events_path"].write_text("\n".join(lines) + "\n", encoding="utf-8")

    api = IdentityTimelineReadOnlyAPI(DirectoryIdentityTimelineRepository(tmp_path))
    encoded = quote(fixture["agent_id"], safe="")
    response = api.handle("GET", f"/api/v1/agents/{encoded}/timeline")
    payload = _payload(response)

    assert response[0] == 200
    assert payload["integrity_status"] == "INVALID"
    assert payload["authoritative"] is False
    assert payload["active_profile"] is None
    assert payload["observed_active_profile"]["version"] == 3
    codes = {item["code"] for item in payload["findings"]}
    assert "EVENT_HASH_MISMATCH" in codes

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(payload))


def test_persisted_projection_mismatch_is_visible_and_fail_closed(tmp_path: Path) -> None:
    fixture = build_timeline_bundle(tmp_path, "agent:mismatch")
    persisted = json.loads(fixture["timeline_path"].read_text(encoding="utf-8"))
    persisted["active_profile"]["traits"]["review_style"] = "tampered"
    unsigned = dict(persisted)
    unsigned.pop("integrity")
    persisted["integrity"]["timeline_digest"] = digest_json(unsigned)
    fixture["timeline_path"].write_text(
        json.dumps(persisted, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    api = IdentityTimelineReadOnlyAPI(DirectoryIdentityTimelineRepository(tmp_path))
    encoded = quote(fixture["agent_id"], safe="")
    payload = _payload(
        api.handle("GET", f"/api/v1/agents/{encoded}/timeline")
    )
    codes = {item["code"] for item in payload["findings"]}

    assert payload["authoritative"] is False
    assert payload["active_profile"] is None
    assert "PERSISTED_PROJECTION_MISMATCH" in codes


def test_health_reports_degraded_without_hiding_invalid_agent(tmp_path: Path) -> None:
    valid = build_timeline_bundle(tmp_path, "agent:valid")
    invalid = build_timeline_bundle(tmp_path, "agent:invalid")
    invalid["events_path"].write_text("not-json\n", encoding="utf-8")
    api = IdentityTimelineReadOnlyAPI(DirectoryIdentityTimelineRepository(tmp_path))

    health = _payload(api.handle("GET", "/api/v1/health"))
    agents = _payload(api.handle("GET", "/api/v1/agents"))["agents"]

    assert health["status"] == "degraded"
    assert health["invalid_timeline_count"] == 1
    assert {item["agent_id"] for item in agents} == {
        valid["agent_id"],
        invalid["agent_id"],
    }
    invalid_item = next(item for item in agents if item["agent_id"] == invalid["agent_id"])
    assert invalid_item["integrity_status"] == "INVALID"
    assert invalid_item["active_profile_version"] is None
