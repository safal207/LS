from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.identity_catalog_trigger import (
    IdentityCatalogTriggerError,
    process_identity_catalog_triggers,
)
from trusted_runtime.identity_control_plane_acceptance import (
    run_identity_control_plane_acceptance,
)
from trusted_runtime.identity_control_plane_viewer import (
    IdentityControlPlaneStatusRepository,
    build_identity_control_plane_viewer,
)


ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_SCHEMA = (
    ROOT / "schemas/trusted_runtime/identity_control_plane_acceptance.schema.json"
)
STATUS_SCHEMA = (
    ROOT / "schemas/trusted_runtime/identity_control_plane_status.schema.json"
)
DASHBOARD_ROOT = (
    ROOT / "python/modules/trusted_runtime/identity_control_plane_dashboard"
)
KEYRING = {"acceptance-key": b"acceptance-key-material"}


def _run(tmp_path: Path):
    return run_identity_control_plane_acceptance(
        tmp_path / "acceptance",
        keyring=KEYRING,
        active_key_id="acceptance-key",
        signing_key_ids=("acceptance-key",),
        audience="internal",
    )


def _request(app, method: str, path: str):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "QUERY_STRING": "",
                "SERVER_NAME": "test",
                "SERVER_PORT": "80",
                "wsgi.url_scheme": "http",
                "wsgi.input": None,
            },
            start_response,
        )
    )
    return captured["status"], captured["headers"], body


def test_one_run_emits_complete_control_plane_evidence(tmp_path: Path) -> None:
    result = _run(tmp_path)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.first_generation == 1
    assert result.repeated_generation == 1
    assert result.second_generation == 2
    assert manifest["result"] == "PASS"
    assert manifest["read_only_viewer"] is True
    assert len(manifest["agents"]) == 2
    assert all(item["verified_episode_count"] == 3 for item in manifest["agents"])
    assert manifest["generation_assertions"] == {
        "first_commit_generation": 1,
        "identical_replay_generation": 1,
        "next_commit_generation": 2,
        "identical_replay_created_no_generation": True,
        "next_commit_incremented_once": True,
    }
    assert manifest["health"]["pending_request_count"] == 0
    assert manifest["health"]["quarantined_request_count"] == 0
    assert manifest["publication"]["generation"] == 2
    assert manifest["publication"]["previous_publication_digest"]

    schema = json.loads(ACCEPTANCE_SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(manifest))

    for agent in (result.first_agent, result.second_agent):
        profile_v1 = json.loads(agent.profile_v1_path.read_text(encoding="utf-8"))
        profile_v2 = json.loads(agent.profile_v2_path.read_text(encoding="utf-8"))
        timeline = json.loads(agent.timeline_path.read_text(encoding="utf-8"))
        assert profile_v1["version"] == 1
        assert profile_v2["version"] == 2
        assert timeline["active_profile"]["version"] == 2
        assert timeline["integrity"]["timeline_digest"] == agent.timeline_digest
        assert timeline["integrity"]["tail_event_ref"] == agent.tail_event_ref
        assert len(agent.episode_paths) == 3

    tamper = json.loads(result.tamper_report_path.read_text(encoding="utf-8"))
    assert tamper["all_fail_closed_checks_passed"] is True


def test_control_plane_status_and_dashboard_are_read_only(tmp_path: Path) -> None:
    result = _run(tmp_path)
    status_repository = IdentityControlPlaneStatusRepository(
        result.publisher_output_root,
        result.trigger_output_root,
        keyring=KEYRING,
        acceptance_manifest_path=result.manifest_path,
    )
    status = status_repository.status()
    assert status["authoritative"] is True
    assert status["integrity_status"] == "VALID"
    assert status["generation"] == 2
    assert status["authoritative_agent_count"] == 2
    assert len(status["trigger"]["tail_event_refs"]) == 1
    assert status["health"]["pending_request_count"] == 0
    assert status["health"]["quarantined_request_count"] == 0

    schema = json.loads(STATUS_SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(status))

    app = build_identity_control_plane_viewer(
        result.dashboard_data_root,
        result.catalog_path,
        result.publisher_output_root,
        result.trigger_output_root,
        catalog_secret=KEYRING["acceptance-key"],
        publication_keyring=KEYRING,
        acceptance_manifest_path=result.manifest_path,
        asset_root=DASHBOARD_ROOT,
    )
    root_status, root_headers, root_body = _request(app, "GET", "/")
    api_status, _, api_body = _request(
        app,
        "GET",
        "/api/v1/control-plane/status",
    )
    mutation_status, mutation_headers, mutation_body = _request(
        app,
        "POST",
        "/api/v1/control-plane/status",
    )

    assert root_status.startswith("200")
    assert b"Identity Control Plane" in root_body
    assert root_headers["Content-Security-Policy"]
    assert api_status.startswith("200")
    assert json.loads(api_body)["authoritative"] is True
    assert mutation_status.startswith("405")
    assert mutation_headers["Allow"] == "GET, HEAD"
    assert b"read-only" in mutation_body.lower()

    javascript = (DASHBOARD_ROOT / "app.js").read_text(encoding="utf-8")
    assert 'method: "GET"' in javascript
    assert 'method: "POST"' not in javascript
    assert 'method: "PUT"' not in javascript
    assert 'method: "DELETE"' not in javascript


def test_changed_trigger_metadata_makes_status_non_authoritative(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path)
    trigger_path = (
        result.trigger_output_root / "identity-catalog-trigger-generation.json"
    )
    payload = json.loads(trigger_path.read_text(encoding="utf-8"))
    payload["generation"] = 999
    trigger_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    status = IdentityControlPlaneStatusRepository(
        result.publisher_output_root,
        result.trigger_output_root,
        keyring=KEYRING,
    ).status()
    codes = {item["code"] for item in status["findings"]}
    assert status["authoritative"] is False
    assert status["integrity_status"] == "INVALID"
    assert "TRIGGER_BATCH_DIGEST_MISMATCH" in codes
    assert "TRIGGER_GENERATION_MISMATCH" in codes


def test_changed_publication_and_timeline_fail_closed(tmp_path: Path) -> None:
    result = _run(tmp_path)
    clean_root = tmp_path / "clean-copy"
    shutil.copytree(result.output_root, clean_root)

    publication_path = (
        result.publisher_output_root / "identity-catalog-publication.json"
    )
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    publication["generation"] = 999
    publication_path.write_text(
        json.dumps(publication, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    status = IdentityControlPlaneStatusRepository(
        result.publisher_output_root,
        result.trigger_output_root,
        keyring=KEYRING,
    ).status()
    assert status["authoritative"] is False
    assert any(
        item["code"] == "PUBLICATION_INTEGRITY_FAILURE" for item in status["findings"]
    )

    timeline_path = (
        clean_root
        / "identity-data"
        / "agent-acceptance-reviewer"
        / "identity-timeline.json"
    )
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    timeline["active_profile"]["traits"]["review_style"] = "tampered"
    timeline_path.write_text(
        json.dumps(timeline, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    app = build_identity_control_plane_viewer(
        clean_root / "identity-data",
        clean_root / "publisher" / "identity-catalog.json",
        clean_root / "publisher",
        clean_root / "trigger",
        catalog_secret=KEYRING["acceptance-key"],
        publication_keyring=KEYRING,
        asset_root=DASHBOARD_ROOT,
    )
    path = "/api/v1/agents/agent%3Aacceptance-reviewer/timeline"
    response_status, _, body = _request(app, "GET", path)
    payload = json.loads(body)
    assert response_status.startswith("200")
    assert payload["authoritative"] is False
    assert payload["active_profile"] is None


def test_changed_outbox_stops_trigger_processing(tmp_path: Path) -> None:
    result = _run(tmp_path)
    outbox_path = result.output_root / "identity-catalog-publication-outbox.jsonl"
    lines = outbox_path.read_text(encoding="utf-8").splitlines()
    changed = json.loads(lines[0])
    changed["actor"] = "tampered:actor"
    lines[0] = json.dumps(changed, sort_keys=True, separators=(",", ":"))
    outbox_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(
        IdentityCatalogTriggerError,
        match="hash chain is invalid",
    ):
        process_identity_catalog_triggers(
            result.dashboard_data_root,
            outbox_path,
            result.publisher_output_root,
            result.trigger_output_root,
            keyring=KEYRING,
            active_key_id="acceptance-key",
            signing_key_ids=("acceptance-key",),
            audience="internal",
            visibility_policy={
                "agent:acceptance-reviewer": ("internal",),
                "agent:acceptance-auditor": ("internal",),
            },
            processed_at="2026-06-24T10:40:00Z",
            stale_after_seconds=86400,
        )
