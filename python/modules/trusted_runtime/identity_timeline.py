"""Append-only persistence and deterministic replay for identity governance.

The durable event store proves hash-chain integrity. This module adds semantic
validation for the identity lifecycle and rebuilds an active profile projection
without rerunning approvals, patches, applications, or side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .persistence import DurableEvent, digest_json


IDENTITY_TIMELINE_VERSION = "trusted_runtime.identity_timeline.v0.1"
IDENTITY_TIMELINE_POLICY_VERSION = "identity_timeline.replay.v0.1"


class IdentityLifecycleEventType(str, Enum):
    PROFILE_RECORDED = "IDENTITY_PROFILE_RECORDED"
    PROPOSAL_RECORDED = "IDENTITY_PROPOSAL_RECORDED"
    APPROVAL_RECORDED = "IDENTITY_APPROVAL_RECORDED"
    PATCH_RECORDED = "IDENTITY_PATCH_RECORDED"
    PATCH_COMMITTED = "IDENTITY_PATCH_COMMITTED"
    APPLICATION_RECORDED = "IDENTITY_APPLICATION_RECORDED"
    ROLLBACK_RECORDED = "IDENTITY_ROLLBACK_RECORDED"


class IdentityTimelineStatus(str, Enum):
    PROFILE_ONLY = "PROFILE_ONLY"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"


class IdentityTimelineError(RuntimeError):
    """Base error for identity lifecycle persistence and replay."""


class IdentityTimelineReplayError(IdentityTimelineError):
    """Raised when durable events are intact but semantically inconsistent."""

    def __init__(
        self,
        message: str,
        findings: Sequence["IdentityTimelineFinding"],
    ) -> None:
        super().__init__(message)
        self.findings = tuple(findings)


@dataclass(frozen=True)
class IdentityTimelineFinding:
    code: str
    message: str
    event_id: Optional[str] = None
    event_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("identity timeline finding fields must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "event_id": self.event_id,
            "event_ref": self.event_ref,
        }


@dataclass(frozen=True)
class IdentityTimelineProjection:
    agent_id: str
    task_id: str
    trail_id: str
    status: IdentityTimelineStatus
    active_profile: Mapping[str, Any]
    profile_versions: tuple[Mapping[str, Any], ...]
    proposal_refs: tuple[str, ...]
    approval_refs: tuple[str, ...]
    patch_refs: tuple[str, ...]
    commit_refs: tuple[str, ...]
    application_refs: tuple[str, ...]
    rollback_refs: tuple[str, ...]
    events: tuple[Mapping[str, Any], ...]
    findings: tuple[IdentityTimelineFinding, ...]
    replay_mode: str = "projection_only"
    side_effects_applied: bool = False
    policy_version: str = IDENTITY_TIMELINE_POLICY_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_TIMELINE_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != IDENTITY_TIMELINE_VERSION:
            raise ValueError(
                f"unsupported identity timeline version: {self.schema_version}"
            )
        if not all((self.agent_id, self.task_id, self.trail_id, self.policy_version)):
            raise ValueError("identity timeline identifiers must not be empty")
        if self.replay_mode != "projection_only":
            raise ValueError("identity replay must remain projection-only")
        if self.side_effects_applied:
            raise ValueError("identity replay cannot apply side effects")
        if not self.profile_versions:
            raise ValueError("identity timeline requires at least one profile")
        if dict(self.active_profile) != dict(self.profile_versions[-1]):
            raise ValueError("active profile must be the last replayed profile")

    @property
    def is_valid(self) -> bool:
        return not self.findings

    def require_valid(self) -> "IdentityTimelineProjection":
        if self.findings:
            raise IdentityTimelineReplayError(
                f"identity timeline {self.trail_id!r} failed semantic replay",
                self.findings,
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "status": self.status.value,
            "active_profile": dict(self.active_profile),
            "profile_versions": [dict(item) for item in self.profile_versions],
            "proposal_refs": list(self.proposal_refs),
            "approval_refs": list(self.approval_refs),
            "patch_refs": list(self.patch_refs),
            "commit_refs": list(self.commit_refs),
            "application_refs": list(self.application_refs),
            "rollback_refs": list(self.rollback_refs),
            "events": [dict(item) for item in self.events],
            "findings": [item.to_dict() for item in self.findings],
            "replay_mode": self.replay_mode,
            "side_effects_applied": self.side_effects_applied,
            "policy_version": self.policy_version,
            "metadata": dict(self.metadata),
        }
        payload["integrity"] = {
            "algorithm": "sha256",
            "event_count": len(self.events),
            "tail_event_ref": self.events[-1]["event_ref"],
            "timeline_digest": digest_json(payload),
        }
        return payload


def identity_task_id(agent_id: str) -> str:
    if not agent_id:
        raise ValueError("agent_id must not be empty")
    return f"identity-task:{agent_id}"


def identity_trail_id(agent_id: str) -> str:
    if not agent_id:
        raise ValueError("agent_id must not be empty")
    return f"identity-trail:{agent_id}"


def persist_identity_lifecycle(
    store: Any,
    *,
    agent_id: str,
    profile_v1: Mapping[str, Any],
    proposal: Mapping[str, Any],
    approval: Mapping[str, Any],
    patch: Optional[Mapping[str, Any]] = None,
    commit: Optional[Mapping[str, Any]] = None,
    application: Optional[Mapping[str, Any]] = None,
    profile_v2: Optional[Mapping[str, Any]] = None,
    rollback: Optional[Mapping[str, Any]] = None,
    profile_v3: Optional[Mapping[str, Any]] = None,
    actor: str = "runtime:identity-timeline",
) -> tuple[str, ...]:
    """Persist one identity lifecycle in deterministic causal order."""

    task_id = identity_task_id(agent_id)
    trail_id = identity_trail_id(agent_id)
    events: list[dict[str, Any]] = []

    profile_v1_event = _event(
        task_id=task_id,
        trail_id=trail_id,
        event_type=IdentityLifecycleEventType.PROFILE_RECORDED,
        stable_id=str(profile_v1["profile_id"]),
        actor=actor,
        created_at=str(profile_v1["created_at"]),
        parent_cause=task_id,
        record=profile_v1,
        agent_id=agent_id,
    )
    events.append(profile_v1_event)

    proposal_event = _event(
        task_id=task_id,
        trail_id=trail_id,
        event_type=IdentityLifecycleEventType.PROPOSAL_RECORDED,
        stable_id=str(proposal["proposal_id"]),
        actor=actor,
        created_at=str(proposal["created_at"]),
        parent_cause=profile_v1_event["event_id"],
        record=proposal,
        agent_id=agent_id,
    )
    events.append(proposal_event)

    approval_event = _event(
        task_id=task_id,
        trail_id=trail_id,
        event_type=IdentityLifecycleEventType.APPROVAL_RECORDED,
        stable_id=str(approval["approval_id"]),
        actor=str(approval["approver_actor"]),
        created_at=str(approval["decided_at"]),
        parent_cause=proposal_event["event_id"],
        record=approval,
        agent_id=agent_id,
    )
    events.append(approval_event)

    if patch is not None:
        patch_event = _event(
            task_id=task_id,
            trail_id=trail_id,
            event_type=IdentityLifecycleEventType.PATCH_RECORDED,
            stable_id=str(patch["patch_id"]),
            actor=str(patch["created_by"]),
            created_at=str(patch["created_at"]),
            parent_cause=approval_event["event_id"],
            record=patch,
            agent_id=agent_id,
        )
        events.append(patch_event)
    else:
        patch_event = None

    if commit is not None:
        if patch_event is None:
            raise IdentityTimelineError("patch commit cannot be persisted without patch")
        commit_event = _event(
            task_id=task_id,
            trail_id=trail_id,
            event_type=IdentityLifecycleEventType.PATCH_COMMITTED,
            stable_id=str(commit["commit_id"]),
            actor=str(commit["committed_by"]),
            created_at=str(commit["committed_at"]),
            parent_cause=patch_event["event_id"],
            record=commit,
            agent_id=agent_id,
        )
        events.append(commit_event)
    else:
        commit_event = None

    if application is not None:
        if commit_event is None:
            raise IdentityTimelineError(
                "identity application cannot be persisted without patch commit"
            )
        application_event = _event(
            task_id=task_id,
            trail_id=trail_id,
            event_type=IdentityLifecycleEventType.APPLICATION_RECORDED,
            stable_id=str(application["application_id"]),
            actor=str(application["activated_by"]),
            created_at=str(application["activated_at"]),
            parent_cause=commit_event["event_id"],
            record=application,
            agent_id=agent_id,
        )
        events.append(application_event)
    else:
        application_event = None

    if profile_v2 is not None:
        if application_event is None:
            raise IdentityTimelineError(
                "activated profile cannot be persisted without application"
            )
        profile_v2_event = _event(
            task_id=task_id,
            trail_id=trail_id,
            event_type=IdentityLifecycleEventType.PROFILE_RECORDED,
            stable_id=str(profile_v2["profile_id"]),
            actor=actor,
            created_at=str(profile_v2["created_at"]),
            parent_cause=application_event["event_id"],
            record=profile_v2,
            agent_id=agent_id,
        )
        events.append(profile_v2_event)
    else:
        profile_v2_event = None

    if rollback is not None:
        if profile_v2_event is None:
            raise IdentityTimelineError(
                "rollback cannot be persisted without activated profile"
            )
        rollback_event = _event(
            task_id=task_id,
            trail_id=trail_id,
            event_type=IdentityLifecycleEventType.ROLLBACK_RECORDED,
            stable_id=str(rollback["rollback_id"]),
            actor=str(rollback["rolled_back_by"]),
            created_at=str(rollback["rolled_back_at"]),
            parent_cause=profile_v2_event["event_id"],
            record=rollback,
            agent_id=agent_id,
        )
        events.append(rollback_event)
    else:
        rollback_event = None

    if profile_v3 is not None:
        if rollback_event is None:
            raise IdentityTimelineError(
                "rollback profile cannot be persisted without rollback record"
            )
        events.append(
            _event(
                task_id=task_id,
                trail_id=trail_id,
                event_type=IdentityLifecycleEventType.PROFILE_RECORDED,
                stable_id=str(profile_v3["profile_id"]),
                actor=actor,
                created_at=str(profile_v3["created_at"]),
                parent_cause=rollback_event["event_id"],
                record=profile_v3,
                agent_id=agent_id,
            )
        )

    return tuple(store.append(event) for event in events)


def scan_identity_timeline(store: Any, *, agent_id: str) -> IdentityTimelineProjection:
    """Rebuild an identity profile projection from durable events only."""

    task_id = identity_task_id(agent_id)
    trail_id = identity_trail_id(agent_id)
    durable_events = tuple(store.read_events(trail_id))
    if not durable_events:
        raise IdentityTimelineReplayError(
            f"identity timeline {trail_id!r} is empty",
            (IdentityTimelineFinding("EMPTY_TIMELINE", "no durable events found"),),
        )

    findings: list[IdentityTimelineFinding] = []
    profiles: list[Mapping[str, Any]] = []
    proposals: dict[str, Mapping[str, Any]] = {}
    approvals: dict[str, Mapping[str, Any]] = {}
    patches: dict[str, Mapping[str, Any]] = {}
    commits: dict[str, Mapping[str, Any]] = {}
    applications: dict[str, Mapping[str, Any]] = {}
    rollbacks: dict[str, Mapping[str, Any]] = {}
    patch_application_ids: dict[str, str] = {}
    event_views: list[Mapping[str, Any]] = []
    event_ids_by_record: dict[str, str] = {}
    status = IdentityTimelineStatus.PROFILE_ONLY

    for event in durable_events:
        event_views.append(_event_view(event))
        envelope = dict(event.payload)
        payload = envelope.get("payload", {})
        record = payload.get("record") if isinstance(payload, Mapping) else None
        event_agent = payload.get("agent_id") if isinstance(payload, Mapping) else None
        if not isinstance(record, Mapping):
            findings.append(_finding("MISSING_RECORD", "event has no record payload", event))
            continue
        if event.task_id != task_id or event.trail_id != trail_id:
            findings.append(_finding("IDENTITY_SCOPE_MISMATCH", "event is outside identity scope", event))
        if event_agent != agent_id:
            findings.append(_finding("AGENT_MISMATCH", "event belongs to another agent", event))

        try:
            event_type = IdentityLifecycleEventType(event.event_type)
        except ValueError:
            findings.append(_finding("UNKNOWN_EVENT_TYPE", "unsupported identity event type", event))
            continue

        if event_type is IdentityLifecycleEventType.PROFILE_RECORDED:
            _replay_profile(record, event, profiles, applications, rollbacks, findings)
            profiles.append(dict(record))
            event_ids_by_record[str(record.get("profile_id"))] = event.event_id
            if int(record.get("version", 0)) > 1 and str(record.get("source_application_ref", "")).startswith("identity-rollback:"):
                status = IdentityTimelineStatus.ROLLED_BACK
            elif int(record.get("version", 0)) > 1:
                status = IdentityTimelineStatus.APPLIED
        elif event_type is IdentityLifecycleEventType.PROPOSAL_RECORDED:
            proposal_id = str(record.get("proposal_id", ""))
            proposals[proposal_id] = dict(record)
            event_ids_by_record[proposal_id] = event.event_id
            status = IdentityTimelineStatus.PENDING
        elif event_type is IdentityLifecycleEventType.APPROVAL_RECORDED:
            approval_id = str(record.get("approval_id", ""))
            approvals[approval_id] = dict(record)
            event_ids_by_record[approval_id] = event.event_id
            _replay_approval(record, event, proposals, findings)
            status = _approval_status(str(record.get("decision", "")))
        elif event_type is IdentityLifecycleEventType.PATCH_RECORDED:
            patch_id = str(record.get("patch_id", ""))
            patches[patch_id] = dict(record)
            event_ids_by_record[patch_id] = event.event_id
            _replay_patch(record, event, proposals, approvals, profiles, findings)
        elif event_type is IdentityLifecycleEventType.PATCH_COMMITTED:
            commit_id = str(record.get("commit_id", ""))
            commits[commit_id] = dict(record)
            event_ids_by_record[commit_id] = event.event_id
            _replay_commit(record, event, patches, findings)
        elif event_type is IdentityLifecycleEventType.APPLICATION_RECORDED:
            application_id = str(record.get("application_id", ""))
            if application_id in applications:
                findings.append(_finding("DUPLICATE_APPLICATION", "application ID appears more than once", event))
            patch_id = str(record.get("patch_id", ""))
            if patch_id in patch_application_ids:
                findings.append(_finding("PATCH_REAPPLIED", "patch is applied more than once", event))
            applications[application_id] = dict(record)
            patch_application_ids[patch_id] = application_id
            event_ids_by_record[application_id] = event.event_id
            _replay_application(record, event, proposals, approvals, patches, commits, profiles, findings)
            status = IdentityTimelineStatus.APPLIED
        elif event_type is IdentityLifecycleEventType.ROLLBACK_RECORDED:
            rollback_id = str(record.get("rollback_id", ""))
            rollbacks[rollback_id] = dict(record)
            event_ids_by_record[rollback_id] = event.event_id
            _replay_rollback(record, event, applications, profiles, findings)
            status = IdentityTimelineStatus.ROLLED_BACK

    if not profiles:
        findings.append(IdentityTimelineFinding("MISSING_PROFILE", "timeline contains no profile snapshot"))
        active_profile: Mapping[str, Any] = {}
        profiles = ({},)  # type: ignore[assignment]
    else:
        active_profile = profiles[-1]

    projection = IdentityTimelineProjection(
        agent_id=agent_id,
        task_id=task_id,
        trail_id=trail_id,
        status=status,
        active_profile=active_profile,
        profile_versions=tuple(dict(item) for item in profiles),
        proposal_refs=tuple(proposals),
        approval_refs=tuple(approvals),
        patch_refs=tuple(patches),
        commit_refs=tuple(commits),
        application_refs=tuple(applications),
        rollback_refs=tuple(rollbacks),
        events=tuple(event_views),
        findings=tuple(findings),
        metadata={
            "event_store_adapter": getattr(store, "adapter_name", "unknown"),
            "reconstructed_from_events": True,
            "models_rerun": False,
            "approvals_rerun": False,
            "patches_reapplied": False,
        },
    )
    return projection


def replay_identity_timeline(store: Any, *, agent_id: str) -> IdentityTimelineProjection:
    return scan_identity_timeline(store, agent_id=agent_id).require_valid()


def _event(
    *,
    task_id: str,
    trail_id: str,
    event_type: IdentityLifecycleEventType,
    stable_id: str,
    actor: str,
    created_at: str,
    parent_cause: str,
    record: Mapping[str, Any],
    agent_id: str,
) -> dict[str, Any]:
    return {
        "event_id": f"event:{event_type.value.lower()}:{stable_id}",
        "task_id": task_id,
        "trail_id": trail_id,
        "event_type": event_type.value,
        "actor": actor,
        "created_at": created_at,
        "parent_cause": parent_cause,
        "evidence_refs": _record_evidence_refs(record),
        "payload": {
            "agent_id": agent_id,
            "record_type": event_type.value,
            "record_digest": digest_json(record),
            "record": dict(record),
        },
    }


def _record_evidence_refs(record: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "proposal_id",
        "approval_id",
        "patch_id",
        "commit_id",
        "application_id",
        "rollback_id",
        "previous_profile_ref",
        "new_profile_ref",
    ):
        value = record.get(key)
        if value:
            values.append(str(value))
    return list(dict.fromkeys(values))


def _event_view(event: DurableEvent) -> dict[str, Any]:
    return {
        "sequence": event.sequence,
        "event_id": event.event_id,
        "event_ref": event.event_ref,
        "event_type": event.event_type,
        "actor": event.actor,
        "created_at": event.created_at,
        "parent_event_id": event.parent_event_id,
        "payload_digest": event.payload_digest,
        "event_hash": event.event_hash,
        "previous_hash": event.previous_hash,
    }


def _replay_profile(
    record: Mapping[str, Any],
    event: DurableEvent,
    profiles: Sequence[Mapping[str, Any]],
    applications: Mapping[str, Mapping[str, Any]],
    rollbacks: Mapping[str, Mapping[str, Any]],
    findings: list[IdentityTimelineFinding],
) -> None:
    version = int(record.get("version", 0))
    if version != len(profiles) + 1:
        findings.append(_finding("PROFILE_VERSION_GAP", "profile versions must increase exactly once", event))
    if version == 1:
        if record.get("previous_profile_ref") is not None:
            findings.append(_finding("INVALID_INITIAL_PROFILE", "profile v1 cannot reference a previous profile", event))
        return
    if not profiles:
        findings.append(_finding("MISSING_PREVIOUS_PROFILE", "versioned profile has no durable predecessor", event))
        return
    previous_ref = _profile_ref(profiles[-1])
    if record.get("previous_profile_ref") != previous_ref:
        findings.append(_finding("PROFILE_PARENT_MISMATCH", "profile previous ref does not match active predecessor", event))
    source_ref = str(record.get("source_application_ref", ""))
    if source_ref.startswith("identity-application:") and source_ref not in applications:
        findings.append(_finding("MISSING_APPLICATION", "profile activation has no application event", event))
    if source_ref.startswith("identity-rollback:") and source_ref not in rollbacks:
        findings.append(_finding("MISSING_ROLLBACK", "rollback profile has no rollback event", event))


def _replay_approval(
    record: Mapping[str, Any],
    event: DurableEvent,
    proposals: Mapping[str, Mapping[str, Any]],
    findings: list[IdentityTimelineFinding],
) -> None:
    proposal_id = str(record.get("proposal_id", ""))
    proposal = proposals.get(proposal_id)
    if proposal is None:
        findings.append(_finding("MISSING_PROPOSAL", "approval has no proposal event", event))
        return
    if record.get("proposal_digest") != digest_json(proposal):
        findings.append(_finding("PROPOSAL_DIGEST_MISMATCH", "approval is not bound to the durable proposal", event))
    if record.get("proposer_actor") == record.get("approver_actor"):
        findings.append(_finding("SELF_APPROVAL", "proposer and approver are the same actor", event))


def _replay_patch(
    record: Mapping[str, Any],
    event: DurableEvent,
    proposals: Mapping[str, Mapping[str, Any]],
    approvals: Mapping[str, Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    findings: list[IdentityTimelineFinding],
) -> None:
    approval = approvals.get(str(record.get("approval_id", "")))
    proposal = proposals.get(str(record.get("proposal_id", "")))
    if approval is None or approval.get("decision") != "APPROVE":
        findings.append(_finding("PATCH_WITHOUT_APPROVAL", "patch requires durable APPROVE decision", event))
    if proposal is None:
        findings.append(_finding("PATCH_WITHOUT_PROPOSAL", "patch requires durable proposal", event))
    elif record.get("proposal_digest") != digest_json(proposal):
        findings.append(_finding("PATCH_PROPOSAL_DIGEST_MISMATCH", "patch proposal digest is invalid", event))
    if not profiles:
        findings.append(_finding("PATCH_WITHOUT_PROFILE", "patch has no base profile", event))
    else:
        if record.get("base_profile_ref") != _profile_ref(profiles[-1]):
            findings.append(_finding("PATCH_BASE_PROFILE_MISMATCH", "patch base profile ref is invalid", event))
        if int(record.get("base_profile_version", 0)) != int(profiles[-1].get("version", 0)):
            findings.append(_finding("PATCH_BASE_VERSION_MISMATCH", "patch base profile version is invalid", event))


def _replay_commit(
    record: Mapping[str, Any],
    event: DurableEvent,
    patches: Mapping[str, Mapping[str, Any]],
    findings: list[IdentityTimelineFinding],
) -> None:
    patch = patches.get(str(record.get("patch_id", "")))
    if patch is None:
        findings.append(_finding("COMMIT_WITHOUT_PATCH", "patch commit has no patch event", event))
    elif record.get("patch_digest") != digest_json(patch):
        findings.append(_finding("PATCH_DIGEST_MISMATCH", "commit does not match durable patch", event))


def _replay_application(
    record: Mapping[str, Any],
    event: DurableEvent,
    proposals: Mapping[str, Mapping[str, Any]],
    approvals: Mapping[str, Mapping[str, Any]],
    patches: Mapping[str, Mapping[str, Any]],
    commits: Mapping[str, Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    findings: list[IdentityTimelineFinding],
) -> None:
    proposal = proposals.get(str(record.get("proposal_id", "")))
    approval = approvals.get(str(record.get("approval_id", "")))
    patch = patches.get(str(record.get("patch_id", "")))
    commit = commits.get(str(record.get("commit_id", "")))
    if proposal is None:
        findings.append(_finding("APPLICATION_WITHOUT_PROPOSAL", "application has no proposal", event))
    if approval is None or approval.get("decision") != "APPROVE":
        findings.append(_finding("APPLICATION_WITHOUT_APPROVAL", "application has no APPROVE decision", event))
    if patch is None:
        findings.append(_finding("APPLICATION_WITHOUT_PATCH", "application has no patch", event))
    if commit is None:
        findings.append(_finding("MISSING_PATCH_COMMIT", "application occurred before durable patch commit", event))
    elif patch is not None and commit.get("patch_digest") != digest_json(patch):
        findings.append(_finding("APPLICATION_COMMIT_MISMATCH", "application commit does not match patch", event))
    if patch is not None and record.get("patch_digest") != digest_json(patch):
        findings.append(_finding("APPLICATION_PATCH_DIGEST_MISMATCH", "application patch digest is invalid", event))
    if profiles and record.get("previous_profile_ref") != _profile_ref(profiles[-1]):
        findings.append(_finding("APPLICATION_PROFILE_MISMATCH", "application previous profile ref is invalid", event))
    if record.get("replay_safe") is not True:
        findings.append(_finding("APPLICATION_NOT_REPLAY_SAFE", "application record is not replay-safe", event))


def _replay_rollback(
    record: Mapping[str, Any],
    event: DurableEvent,
    applications: Mapping[str, Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    findings: list[IdentityTimelineFinding],
) -> None:
    application = applications.get(str(record.get("application_id", "")))
    if application is None:
        findings.append(_finding("ROLLBACK_WITHOUT_APPLICATION", "rollback has no application event", event))
        return
    known_profile_refs = {_profile_ref(item) for item in profiles}
    if record.get("from_profile_ref") not in known_profile_refs:
        findings.append(_finding("ROLLBACK_FROM_PROFILE_MISSING", "rollback source profile is not durable", event))
    if record.get("restored_from_profile_ref") not in known_profile_refs:
        findings.append(_finding("ROLLBACK_TARGET_PROFILE_MISSING", "rollback target profile is not durable", event))
    if profiles and record.get("from_profile_ref") != _profile_ref(profiles[-1]):
        findings.append(_finding("ROLLBACK_ACTIVE_PROFILE_MISMATCH", "rollback does not start from active profile", event))


def _approval_status(decision: str) -> IdentityTimelineStatus:
    return {
        "APPROVE": IdentityTimelineStatus.APPROVED,
        "REJECT": IdentityTimelineStatus.REJECTED,
        "EXPIRE": IdentityTimelineStatus.EXPIRED,
        "INVALIDATE": IdentityTimelineStatus.INVALIDATED,
    }.get(decision, IdentityTimelineStatus.PENDING)


def _profile_ref(profile: Mapping[str, Any]) -> str:
    return "identity-profile:sha256:" + digest_json(profile)


def _finding(code: str, message: str, event: DurableEvent) -> IdentityTimelineFinding:
    return IdentityTimelineFinding(code, message, event.event_id, event.event_ref)
