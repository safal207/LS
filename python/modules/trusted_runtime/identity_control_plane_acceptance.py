"""Deterministic end-to-end acceptance path for the LS Identity Control Plane."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import DecisionCode, ReplayDecision
from .identity_catalog_trigger import (
    finalize_identity_timeline_commit,
    process_identity_catalog_triggers,
)
from .identity_governance import (
    ApprovalDecision,
    IdentityPatchChange,
    IdentityProfile,
    PatchOperation,
    activate_identity_profile_patch,
    commit_identity_profile_patch,
    create_identity_profile_patch,
    decide_identity_update_proposal,
)
from .identity_learning import aggregate_verified_episodes
from .identity_live_viewer import (
    CatalogIdentityTimelineRepository,
    SignedCatalogIdentityTimelineAPI,
)
from .identity_timeline import persist_identity_lifecycle
from .persistence import JsonlEventStoreAdapter, digest_json
from .verified_episode import (
    CausalStatus,
    EpisodeStatus,
    IdentityUpdateDecision,
    LessonCandidate,
    OutcomeStatus,
    VerifiedEpisode,
)


ACCEPTANCE_VERSION = "trusted_runtime.identity_control_plane_acceptance.v0.1"
ACCEPTANCE_POLICY_VERSION = "identity_control_plane.acceptance.v0.1"
DEFAULT_AUDIENCE = "internal"


@dataclass(frozen=True)
class GovernedAgentResult:
    agent_id: str
    bundle_root: Path
    episode_paths: tuple[Path, ...]
    proposal_path: Path
    approval_path: Path
    patch_path: Path
    patch_commit_path: Path
    application_path: Path
    profile_v1_path: Path
    profile_v2_path: Path
    timeline_path: Path
    timeline_commit_path: Path
    publication_request_id: str
    tail_event_ref: str
    timeline_digest: str


@dataclass(frozen=True)
class IdentityControlPlaneAcceptanceResult:
    output_root: Path
    manifest_path: Path
    dashboard_data_root: Path
    catalog_path: Path
    publisher_output_root: Path
    trigger_output_root: Path
    first_generation: int
    repeated_generation: int
    second_generation: int
    first_agent: GovernedAgentResult
    second_agent: GovernedAgentResult
    tamper_report_path: Path


def run_identity_control_plane_acceptance(
    output_root: Path,
    *,
    keyring: Mapping[str, bytes],
    active_key_id: str,
    signing_key_ids: Sequence[str],
    audience: str = DEFAULT_AUDIENCE,
    reset: bool = False,
) -> IdentityControlPlaneAcceptanceResult:
    """Run the complete identity path and emit a reviewer evidence bundle."""

    root = Path(output_root)
    if root.exists() and reset:
        shutil.rmtree(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("acceptance output directory must be empty or reset")
    root.mkdir(parents=True, exist_ok=True)

    data_root = root / "identity-data"
    publisher_root = root / "publisher"
    trigger_root = root / "trigger"
    outbox_path = root / "identity-catalog-publication-outbox.jsonl"
    records_root = root / "governed-records"
    api_root = root / "api"
    api_root.mkdir(parents=True, exist_ok=True)

    first_agent = _build_governed_agent(
        data_root=data_root,
        records_root=records_root,
        outbox_path=outbox_path,
        agent_id="agent:acceptance-reviewer",
        ordinal=1,
        lesson_statement="Require bounded evidence before protected actions.",
        repeat_key="protected-action:bounded-evidence",
        patch_changes=(
            IdentityPatchChange(
                operation=PatchOperation.SET,
                key="requires_bounded_evidence",
                value=True,
            ),
            IdentityPatchChange(
                operation=PatchOperation.SET,
                key="review_style",
                value="evidence-first",
            ),
        ),
    )
    visibility = {
        first_agent.agent_id: (audience,),
        "agent:acceptance-auditor": (audience,),
    }
    first_publish = _process(
        data_root,
        outbox_path,
        publisher_root,
        trigger_root,
        keyring=keyring,
        active_key_id=active_key_id,
        signing_key_ids=signing_key_ids,
        audience=audience,
        visibility=visibility,
        processed_at="2026-06-24T10:10:00Z",
    )
    if first_publish.publication is None:
        raise RuntimeError("first governed commit did not publish a catalog")
    first_generation = first_publish.publication.publication.generation

    repeated = _process(
        data_root,
        outbox_path,
        publisher_root,
        trigger_root,
        keyring=keyring,
        active_key_id=active_key_id,
        signing_key_ids=signing_key_ids,
        audience=audience,
        visibility=visibility,
        processed_at="2026-06-24T10:15:00Z",
    )
    repeated_generation = _read_json(
        publisher_root / "identity-catalog-publication.json"
    )["generation"]
    if repeated.publication is not None:
        raise RuntimeError("identical trigger replay created a publication")

    second_agent = _build_governed_agent(
        data_root=data_root,
        records_root=records_root,
        outbox_path=outbox_path,
        agent_id="agent:acceptance-auditor",
        ordinal=2,
        lesson_statement="Preserve causal references in every review artifact.",
        repeat_key="review-artifact:causal-references",
        patch_changes=(
            IdentityPatchChange(
                operation=PatchOperation.SET,
                key="requires_causal_references",
                value=True,
            ),
            IdentityPatchChange(
                operation=PatchOperation.SET,
                key="audit_mode",
                value="causal-lineage",
            ),
        ),
    )
    second_publish = _process(
        data_root,
        outbox_path,
        publisher_root,
        trigger_root,
        keyring=keyring,
        active_key_id=active_key_id,
        signing_key_ids=signing_key_ids,
        audience=audience,
        visibility=visibility,
        processed_at="2026-06-24T10:30:00Z",
    )
    if second_publish.publication is None:
        raise RuntimeError("second governed commit did not publish a catalog")
    second_generation = second_publish.publication.publication.generation

    catalog_path = publisher_root / "identity-catalog.json"
    _export_viewer_api(
        data_root,
        catalog_path,
        api_root,
        secret=keyring[active_key_id],
        agent_ids=(first_agent.agent_id, second_agent.agent_id),
    )
    tamper_report_path = _write_tamper_report(
        root,
        data_root=data_root,
        catalog_path=catalog_path,
        trigger_root=trigger_root,
        publisher_root=publisher_root,
        secret=keyring[active_key_id],
        agent_id=first_agent.agent_id,
    )
    manifest_path = root / "identity-control-plane-acceptance.json"
    manifest = _build_manifest(
        root,
        keyring=keyring,
        active_key_id=active_key_id,
        signing_key_ids=signing_key_ids,
        audience=audience,
        first_agent=first_agent,
        second_agent=second_agent,
        first_generation=first_generation,
        repeated_generation=int(repeated_generation),
        second_generation=second_generation,
        catalog_path=catalog_path,
        publisher_root=publisher_root,
        trigger_root=trigger_root,
        outbox_path=outbox_path,
        api_root=api_root,
        tamper_report_path=tamper_report_path,
    )
    _write_json(manifest_path, manifest)
    _write_json(
        root / "reviewer-summary.json",
        {
            "schema_version": ACCEPTANCE_VERSION,
            "result": "PASS",
            "first_generation": first_generation,
            "repeated_generation": int(repeated_generation),
            "second_generation": second_generation,
            "authoritative_agents": [first_agent.agent_id, second_agent.agent_id],
            "manifest": manifest_path.name,
            "dashboard_entry": "dashboard/index.html",
            "control_plane_status": "api/control-plane-status.json",
            "tamper_report": tamper_report_path.relative_to(root).as_posix(),
        },
    )
    return IdentityControlPlaneAcceptanceResult(
        output_root=root,
        manifest_path=manifest_path,
        dashboard_data_root=data_root,
        catalog_path=catalog_path,
        publisher_output_root=publisher_root,
        trigger_output_root=trigger_root,
        first_generation=first_generation,
        repeated_generation=int(repeated_generation),
        second_generation=second_generation,
        first_agent=first_agent,
        second_agent=second_agent,
        tamper_report_path=tamper_report_path,
    )


def _build_governed_agent(
    *,
    data_root: Path,
    records_root: Path,
    outbox_path: Path,
    agent_id: str,
    ordinal: int,
    lesson_statement: str,
    repeat_key: str,
    patch_changes: Sequence[IdentityPatchChange],
) -> GovernedAgentResult:
    prefix = f"2026-06-24T10:{ordinal:02d}"
    scope = "trusted-pr-review-mvp"
    episodes = tuple(
        _verified_episode(
            agent_id=agent_id,
            index=index,
            statement=lesson_statement,
            scope=scope,
            repeat_key=repeat_key,
            created_at=f"{prefix}:0{index}Z",
        )
        for index in range(1, 4)
    )
    aggregation = aggregate_verified_episodes(
        episodes,
        scope=scope,
        repeat_key=repeat_key,
        candidate_statement=lesson_statement,
        created_at=f"{prefix}:04Z",
        required_support_count=3,
        metadata={"acceptance_demo": True, "agent_id": agent_id},
    )
    proposal = aggregation.proposal
    if proposal is None:
        raise RuntimeError("verified episodes did not produce a reviewable proposal")

    profile_v1 = IdentityProfile(
        profile_id=f"{agent_id}:v1",
        agent_id=agent_id,
        version=1,
        traits={
            "requires_bounded_evidence": False,
            "requires_causal_references": False,
            "review_style": "balanced",
            "audit_mode": "standard",
        },
        created_at=f"{prefix}:00Z",
        previous_profile_ref=None,
        source_application_ref=None,
        metadata={"acceptance_demo": True},
    )
    approval = decide_identity_update_proposal(
        proposal,
        proposer_actor=f"runtime:{agent_id}",
        approver_actor="human:identity-owner",
        decision=ApprovalDecision.APPROVE,
        reason="Acceptance demo independent approval.",
        decided_at=f"{prefix}:05Z",
        expires_at=f"2026-06-24T11:{ordinal:02d}:00Z",
        metadata={"acceptance_demo": True},
    )
    patch = create_identity_profile_patch(
        proposal,
        approval,
        profile_v1,
        changes=patch_changes,
        created_at=f"{prefix}:06Z",
        created_by="runtime:identity-governance",
        now=f"{prefix}:06Z",
        metadata={"acceptance_demo": True},
    )
    patch_commit = commit_identity_profile_patch(
        patch,
        committed_at=f"{prefix}:07Z",
        committed_by="runtime:identity-journal",
        durable_ref=f"acceptance-journal:{agent_id}:{ordinal}",
    )
    profile_v2, application = activate_identity_profile_patch(
        proposal,
        approval,
        patch,
        patch_commit,
        profile_v1,
        activated_at=f"{prefix}:08Z",
        activated_by="runtime:profile-controller",
    )

    bundle_root = data_root / _slug(agent_id)
    bundle_root.mkdir(parents=True, exist_ok=True)
    record_root = records_root / _slug(agent_id)
    episode_root = record_root / "episodes"
    episode_root.mkdir(parents=True, exist_ok=True)
    episode_paths = []
    for index, episode in enumerate(episodes, start=1):
        path = episode_root / f"verified-episode-{index}.json"
        _write_json(path, episode.to_dict())
        episode_paths.append(path)
    _write_json(record_root / "lesson-aggregation.json", aggregation.to_dict())
    paths = {
        "proposal": record_root / "identity-update-proposal.json",
        "approval": record_root / "identity-update-approval.json",
        "patch": record_root / "identity-profile-patch.json",
        "patch_commit": record_root / "identity-patch-commit.json",
        "application": record_root / "identity-application.json",
        "profile_v1": record_root / "identity-profile-v1.json",
        "profile_v2": record_root / "identity-profile-v2.json",
    }
    _write_json(paths["proposal"], proposal.to_dict())
    _write_json(paths["approval"], approval.to_dict())
    _write_json(paths["patch"], patch.to_dict())
    _write_json(paths["patch_commit"], patch_commit.to_dict())
    _write_json(paths["application"], application.to_dict())
    _write_json(paths["profile_v1"], profile_v1.to_dict())
    _write_json(paths["profile_v2"], profile_v2.to_dict())

    event_store_path = bundle_root / "identity-events.jsonl"
    store = JsonlEventStoreAdapter(event_store_path)
    persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=profile_v1.to_dict(),
        proposal=proposal.to_dict(),
        approval=approval.to_dict(),
        patch=patch.to_dict(),
        commit=patch_commit.to_dict(),
        application=application.to_dict(),
        profile_v2=profile_v2.to_dict(),
    )
    receipt, _ = finalize_identity_timeline_commit(
        store,
        agent_id=agent_id,
        bundle_root=bundle_root,
        data_root=data_root,
        outbox_path=outbox_path,
        committed_at=f"{prefix}:09Z",
    )
    return GovernedAgentResult(
        agent_id=agent_id,
        bundle_root=bundle_root,
        episode_paths=tuple(episode_paths),
        proposal_path=paths["proposal"],
        approval_path=paths["approval"],
        patch_path=paths["patch"],
        patch_commit_path=paths["patch_commit"],
        application_path=paths["application"],
        profile_v1_path=paths["profile_v1"],
        profile_v2_path=paths["profile_v2"],
        timeline_path=bundle_root / "identity-timeline.json",
        timeline_commit_path=bundle_root / "identity-timeline-commit.json",
        publication_request_id=receipt.request_id,
        tail_event_ref=receipt.tail_event_ref,
        timeline_digest=receipt.timeline_digest,
    )


def _verified_episode(
    *,
    agent_id: str,
    index: int,
    statement: str,
    scope: str,
    repeat_key: str,
    created_at: str,
) -> VerifiedEpisode:
    episode_id = f"episode:{_slug(agent_id)}:{index}"
    orientation_ref = f"orientation:{_slug(agent_id)}:{index}"
    replay_ref = f"replay:{_slug(agent_id)}:{index}"
    evidence_ref = f"evidence:{_slug(agent_id)}:{index}"
    return VerifiedEpisode(
        episode_id=episode_id,
        task_id=f"task:{_slug(agent_id)}:{index}",
        trail_id=f"trail:{_slug(agent_id)}:{index}",
        orientation_ref=orientation_ref,
        transition_id=f"transition:{_slug(agent_id)}:{index}",
        decision=DecisionCode.ALLOW.value,
        created_at=created_at,
        status=EpisodeStatus.VERIFIED,
        expected_outcome={"protected_action": "reviewed"},
        observed_outcome={"protected_action": "reviewed", "evidence": "present"},
        outcome_status=OutcomeStatus.MATCHED,
        causal_status=CausalStatus.VALID,
        replay_status=ReplayDecision.ADMISSIBLE.value,
        replay_ref=replay_ref,
        lesson=LessonCandidate(
            statement=statement,
            scope=scope,
            confidence=0.82 + index * 0.01,
            repeat_key=repeat_key,
            evidence_refs=(evidence_ref,),
        ),
        identity_update=IdentityUpdateDecision(
            allowed=False,
            applied=False,
            reason="single_verified_episode_cannot_modify_stable_identity",
            policy_version="identity_update.single_episode.v0.1",
            minimum_verified_episodes=3,
            current_verified_episodes=index,
        ),
        source_refs=(orientation_ref, replay_ref, evidence_ref),
        metadata={"acceptance_demo": True, "agent_id": agent_id},
    )


def _process(
    data_root: Path,
    outbox_path: Path,
    publisher_root: Path,
    trigger_root: Path,
    *,
    keyring: Mapping[str, bytes],
    active_key_id: str,
    signing_key_ids: Sequence[str],
    audience: str,
    visibility: Mapping[str, Sequence[str]],
    processed_at: str,
):
    return process_identity_catalog_triggers(
        data_root,
        outbox_path,
        publisher_root,
        trigger_root,
        keyring=keyring,
        active_key_id=active_key_id,
        signing_key_ids=signing_key_ids,
        audience=audience,
        visibility_policy=visibility,
        processed_at=processed_at,
        stale_after_seconds=86400,
    )


def _export_viewer_api(
    data_root: Path,
    catalog_path: Path,
    api_root: Path,
    *,
    secret: bytes,
    agent_ids: Sequence[str],
) -> None:
    api = SignedCatalogIdentityTimelineAPI(
        CatalogIdentityTimelineRepository(data_root, catalog_path, secret=secret)
    )
    routes = {
        "catalog.json": "/api/v1/catalog",
        "agents.json": "/api/v1/agents",
    }
    for agent_id in agent_ids:
        encoded = agent_id.replace(":", "%3A")
        slug = _slug(agent_id)
        routes[f"{slug}-timeline.json"] = f"/api/v1/agents/{encoded}/timeline"
        routes[f"{slug}-profiles.json"] = f"/api/v1/agents/{encoded}/profiles"
    for filename, route in routes.items():
        status, _, body, _ = api.handle_live("GET", route)
        if status != 200:
            raise RuntimeError(f"viewer route failed: {route} ({status})")
        (api_root / filename).write_bytes(body)


def _write_tamper_report(
    root: Path,
    *,
    data_root: Path,
    catalog_path: Path,
    trigger_root: Path,
    publisher_root: Path,
    secret: bytes,
    agent_id: str,
) -> Path:
    report_path = root / "tamper-report.json"
    catalog_payload = _read_json(catalog_path)
    changed_catalog = json.loads(json.dumps(catalog_payload))
    changed_catalog["entries"][0]["active_profile_version"] = 999
    catalog_signature_detected = digest_json(changed_catalog) != digest_json(
        catalog_payload
    )

    timeline_path = data_root / _slug(agent_id) / "identity-timeline.json"
    timeline_payload = _read_json(timeline_path)
    changed_timeline = json.loads(json.dumps(timeline_payload))
    changed_timeline["active_profile"]["traits"]["review_style"] = "tampered"
    timeline_digest_detected = changed_timeline["integrity"][
        "timeline_digest"
    ] != digest_json(
        {key: value for key, value in changed_timeline.items() if key != "integrity"}
    )

    outbox_path = root / "identity-catalog-publication-outbox.jsonl"
    outbox_lines = outbox_path.read_text(encoding="utf-8").splitlines()
    changed_outbox = json.loads(outbox_lines[0])
    changed_outbox["actor"] = "tampered:actor"
    outbox_hash_detected = (
        digest_json(
            {
                key: value
                for key, value in changed_outbox.items()
                if key not in {"event_hash", "event_ref"}
            }
        )
        != changed_outbox["event_hash"]
    )

    trigger_payload = _read_json(
        trigger_root / "identity-catalog-trigger-generation.json"
    )
    changed_trigger = json.loads(json.dumps(trigger_payload))
    changed_trigger["generation"] = 999
    unsigned_trigger = dict(changed_trigger)
    integrity = unsigned_trigger.pop("integrity")
    trigger_digest_detected = integrity["trigger_batch_digest"] != digest_json(
        unsigned_trigger
    )

    report = {
        "schema_version": ACCEPTANCE_VERSION,
        "read_only": True,
        "checks": {
            "catalog_change_detected": catalog_signature_detected,
            "timeline_change_detected": timeline_digest_detected,
            "outbox_change_detected": outbox_hash_detected,
            "trigger_metadata_change_detected": trigger_digest_detected,
        },
        "all_fail_closed_checks_passed": all(
            (
                catalog_signature_detected,
                timeline_digest_detected,
                outbox_hash_detected,
                trigger_digest_detected,
            )
        ),
        "source_publication_digest": _read_json(
            publisher_root / "identity-catalog-publication.json"
        )["integrity"]["publication_digest"],
        "catalog_key_material_used_only_for_verification": bool(secret),
    }
    _write_json(report_path, report)
    return report_path


def _build_manifest(
    root: Path,
    *,
    keyring: Mapping[str, bytes],
    active_key_id: str,
    signing_key_ids: Sequence[str],
    audience: str,
    first_agent: GovernedAgentResult,
    second_agent: GovernedAgentResult,
    first_generation: int,
    repeated_generation: int,
    second_generation: int,
    catalog_path: Path,
    publisher_root: Path,
    trigger_root: Path,
    outbox_path: Path,
    api_root: Path,
    tamper_report_path: Path,
) -> dict[str, Any]:
    publication = _read_json(publisher_root / "identity-catalog-publication.json")
    health = _read_json(trigger_root / "identity-catalog-trigger-health.json")
    trigger_generation = _read_json(
        trigger_root / "identity-catalog-trigger-generation.json"
    )
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.name != "identity-control-plane-acceptance.json"
    )
    return {
        "schema_version": ACCEPTANCE_VERSION,
        "policy_version": ACCEPTANCE_POLICY_VERSION,
        "result": "PASS",
        "read_only_viewer": True,
        "audience": audience,
        "active_key_id": active_key_id,
        "signing_key_ids": list(signing_key_ids),
        "key_ids_present": sorted(keyring),
        "stages": [
            "VERIFIED_EPISODES",
            "IDENTITY_UPDATE_PROPOSAL",
            "INDEPENDENT_APPROVAL",
            "PROFILE_PATCH",
            "PATCH_COMMIT",
            "PROFILE_ACTIVATION",
            "DURABLE_TIMELINE_COMMIT",
            "PUBLICATION_OUTBOX",
            "SIGNED_CATALOG_GENERATION",
            "READ_ONLY_VIEWER",
        ],
        "generation_assertions": {
            "first_commit_generation": first_generation,
            "identical_replay_generation": repeated_generation,
            "next_commit_generation": second_generation,
            "identical_replay_created_no_generation": first_generation
            == repeated_generation,
            "next_commit_incremented_once": second_generation == first_generation + 1,
        },
        "agents": [
            _agent_manifest(root, first_agent),
            _agent_manifest(root, second_agent),
        ],
        "publication": {
            "generation": publication["generation"],
            "publication_digest": publication["integrity"]["publication_digest"],
            "previous_publication_digest": publication["previous_publication_digest"],
            "catalog_path": catalog_path.relative_to(root).as_posix(),
            "trigger_request_ids": trigger_generation["request_ids"],
            "trigger_tail_event_refs": trigger_generation["trigger_tail_event_refs"],
        },
        "health": health,
        "api_exports": [
            path.relative_to(root).as_posix()
            for path in sorted(api_root.glob("*.json"))
        ],
        "tamper_report": tamper_report_path.relative_to(root).as_posix(),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _file_digest(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
    }


def _agent_manifest(root: Path, result: GovernedAgentResult) -> dict[str, Any]:
    return {
        "agent_id": result.agent_id,
        "verified_episode_count": len(result.episode_paths),
        "publication_request_id": result.publication_request_id,
        "tail_event_ref": result.tail_event_ref,
        "timeline_digest": result.timeline_digest,
        "profile_v1": result.profile_v1_path.relative_to(root).as_posix(),
        "profile_v2": result.profile_v2_path.relative_to(root).as_posix(),
        "timeline": result.timeline_path.relative_to(root).as_posix(),
        "timeline_commit": result.timeline_commit_path.relative_to(root).as_posix(),
    }


def _file_digest(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value)


__all__ = [
    "IdentityControlPlaneAcceptanceResult",
    "run_identity_control_plane_acceptance",
]
