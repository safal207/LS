"""Approval, reversible application, and rollback for identity proposals.

Every stage is immutable and digest-bound:

proposal -> approval -> patch -> commit -> activation -> optional rollback

No proposal, approval, replay record, or patch mutates a profile by itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .identity_learning import IdentityUpdateProposal


IDENTITY_APPROVAL_VERSION = "trusted_runtime.identity_update_approval.v0.1"
IDENTITY_PROFILE_VERSION = "trusted_runtime.identity_profile.v0.1"
IDENTITY_PATCH_VERSION = "trusted_runtime.identity_profile_patch.v0.1"
IDENTITY_PATCH_COMMIT_VERSION = "trusted_runtime.identity_patch_commit.v0.1"
IDENTITY_APPLICATION_VERSION = "trusted_runtime.identity_application.v0.1"
IDENTITY_ROLLBACK_VERSION = "trusted_runtime.identity_rollback.v0.1"
IDENTITY_GOVERNANCE_POLICY_VERSION = "identity_governance.v0.1"


class ApprovalDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EXPIRE = "EXPIRE"
    INVALIDATE = "INVALIDATE"


class PatchOperation(str, Enum):
    SET = "SET"
    REMOVE = "REMOVE"


class IdentityGovernanceError(ValueError):
    """Raised when identity governance would violate a fail-closed boundary."""


class IdentityAlreadyAppliedError(IdentityGovernanceError):
    """Raised when replay would reapply an already activated patch."""


@dataclass(frozen=True)
class IdentityUpdateApproval:
    approval_id: str
    proposal_id: str
    proposal_digest: str
    proposer_actor: str
    approver_actor: str
    decision: ApprovalDecision
    reason: str
    decided_at: str
    expires_at: Optional[str]
    contradiction_refs: tuple[str, ...] = ()
    policy_version: str = IDENTITY_GOVERNANCE_POLICY_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_APPROVAL_VERSION

    def __post_init__(self) -> None:
        required = (
            self.approval_id,
            self.proposal_id,
            self.proposal_digest,
            self.proposer_actor,
            self.approver_actor,
            self.reason,
            self.decided_at,
            self.policy_version,
        )
        if not all(required):
            raise ValueError("identity approval fields must not be empty")
        if self.schema_version != IDENTITY_APPROVAL_VERSION:
            raise ValueError(f"unsupported approval version: {self.schema_version}")
        if self.proposer_actor == self.approver_actor:
            raise ValueError("identity proposal self-approval is prohibited")
        if len(self.contradiction_refs) != len(set(self.contradiction_refs)):
            raise ValueError("contradiction refs must be unique")
        if self.decision is ApprovalDecision.APPROVE:
            if self.expires_at is None:
                raise ValueError("approved identity proposal requires expiry")
            if self.contradiction_refs:
                raise ValueError("contradicted proposal cannot be approved")
            if _instant(self.expires_at) <= _instant(self.decided_at):
                raise ValueError("approval expiry must be after decision time")
        elif self.expires_at is not None:
            raise ValueError("non-approved decision must not grant an expiry window")
        if self.decision is ApprovalDecision.INVALIDATE and not self.contradiction_refs:
            raise ValueError("invalidation requires contradictory evidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "approval_id": self.approval_id,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "proposer_actor": self.proposer_actor,
            "approver_actor": self.approver_actor,
            "decision": self.decision.value,
            "reason": self.reason,
            "decided_at": self.decided_at,
            "expires_at": self.expires_at,
            "contradiction_refs": list(self.contradiction_refs),
            "policy_version": self.policy_version,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IdentityProfile:
    profile_id: str
    agent_id: str
    version: int
    traits: Mapping[str, Any]
    created_at: str
    previous_profile_ref: Optional[str]
    source_application_ref: Optional[str]
    active: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_PROFILE_VERSION

    def __post_init__(self) -> None:
        if not all((self.profile_id, self.agent_id, self.created_at)):
            raise ValueError("identity profile fields must not be empty")
        if self.schema_version != IDENTITY_PROFILE_VERSION:
            raise ValueError(f"unsupported profile version: {self.schema_version}")
        if self.version < 1:
            raise ValueError("profile version must be positive")
        if self.version == 1 and self.previous_profile_ref is not None:
            raise ValueError("initial profile cannot have a previous profile")
        if self.version > 1 and self.previous_profile_ref is None:
            raise ValueError("versioned profile must preserve previous profile ref")

    @property
    def profile_ref(self) -> str:
        return "identity-profile:sha256:" + _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "agent_id": self.agent_id,
            "version": self.version,
            "traits": dict(self.traits),
            "created_at": self.created_at,
            "previous_profile_ref": self.previous_profile_ref,
            "source_application_ref": self.source_application_ref,
            "active": self.active,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IdentityPatchChange:
    operation: PatchOperation
    key: str
    value: Any = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("identity patch key must not be empty")
        if self.operation is PatchOperation.REMOVE and self.value is not None:
            raise ValueError("REMOVE patch operation must not carry a value")

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation.value,
            "key": self.key,
            "value": self.value,
        }


@dataclass(frozen=True)
class IdentityProfilePatch:
    patch_id: str
    proposal_id: str
    proposal_digest: str
    approval_id: str
    agent_id: str
    base_profile_ref: str
    base_profile_version: int
    changes: tuple[IdentityPatchChange, ...]
    created_at: str
    created_by: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_PATCH_VERSION

    def __post_init__(self) -> None:
        required = (
            self.patch_id,
            self.proposal_id,
            self.proposal_digest,
            self.approval_id,
            self.agent_id,
            self.base_profile_ref,
            self.created_at,
            self.created_by,
        )
        if not all(required):
            raise ValueError("identity patch fields must not be empty")
        if self.schema_version != IDENTITY_PATCH_VERSION:
            raise ValueError(f"unsupported patch version: {self.schema_version}")
        if self.base_profile_version < 1:
            raise ValueError("base profile version must be positive")
        if not self.changes:
            raise ValueError("identity patch requires at least one change")
        keys = tuple(change.key for change in self.changes)
        if len(keys) != len(set(keys)):
            raise ValueError("identity patch keys must be unique")

    @property
    def patch_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "patch_id": self.patch_id,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "approval_id": self.approval_id,
            "agent_id": self.agent_id,
            "base_profile_ref": self.base_profile_ref,
            "base_profile_version": self.base_profile_version,
            "changes": [change.to_dict() for change in self.changes],
            "created_at": self.created_at,
            "created_by": self.created_by,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IdentityPatchCommit:
    commit_id: str
    patch_id: str
    patch_digest: str
    committed_at: str
    committed_by: str
    durable_ref: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_PATCH_COMMIT_VERSION

    def __post_init__(self) -> None:
        if not all(
            (
                self.commit_id,
                self.patch_id,
                self.patch_digest,
                self.committed_at,
                self.committed_by,
                self.durable_ref,
            )
        ):
            raise ValueError("identity patch commit fields must not be empty")
        if self.schema_version != IDENTITY_PATCH_COMMIT_VERSION:
            raise ValueError(f"unsupported patch commit version: {self.schema_version}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "commit_id": self.commit_id,
            "patch_id": self.patch_id,
            "patch_digest": self.patch_digest,
            "committed_at": self.committed_at,
            "committed_by": self.committed_by,
            "durable_ref": self.durable_ref,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IdentityApplicationRecord:
    application_id: str
    proposal_id: str
    approval_id: str
    patch_id: str
    patch_digest: str
    commit_id: str
    agent_id: str
    previous_profile_ref: str
    new_profile_ref: str
    previous_version: int
    new_version: int
    activated_at: str
    activated_by: str
    replay_safe: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_APPLICATION_VERSION

    def __post_init__(self) -> None:
        required = (
            self.application_id,
            self.proposal_id,
            self.approval_id,
            self.patch_id,
            self.patch_digest,
            self.commit_id,
            self.agent_id,
            self.previous_profile_ref,
            self.new_profile_ref,
            self.activated_at,
            self.activated_by,
        )
        if not all(required):
            raise ValueError("identity application fields must not be empty")
        if self.schema_version != IDENTITY_APPLICATION_VERSION:
            raise ValueError(
                f"unsupported identity application version: {self.schema_version}"
            )
        if self.new_version != self.previous_version + 1:
            raise ValueError("identity application must increment version exactly once")
        if not self.replay_safe:
            raise ValueError("identity application must be replay-safe")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "application_id": self.application_id,
            "proposal_id": self.proposal_id,
            "approval_id": self.approval_id,
            "patch_id": self.patch_id,
            "patch_digest": self.patch_digest,
            "commit_id": self.commit_id,
            "agent_id": self.agent_id,
            "previous_profile_ref": self.previous_profile_ref,
            "new_profile_ref": self.new_profile_ref,
            "previous_version": self.previous_version,
            "new_version": self.new_version,
            "activated_at": self.activated_at,
            "activated_by": self.activated_by,
            "replay_safe": self.replay_safe,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IdentityRollbackRecord:
    rollback_id: str
    agent_id: str
    application_id: str
    from_profile_ref: str
    restored_from_profile_ref: str
    rollback_profile_ref: str
    from_version: int
    rollback_version: int
    reason: str
    rolled_back_at: str
    rolled_back_by: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IDENTITY_ROLLBACK_VERSION

    def __post_init__(self) -> None:
        required = (
            self.rollback_id,
            self.agent_id,
            self.application_id,
            self.from_profile_ref,
            self.restored_from_profile_ref,
            self.rollback_profile_ref,
            self.reason,
            self.rolled_back_at,
            self.rolled_back_by,
        )
        if not all(required):
            raise ValueError("identity rollback fields must not be empty")
        if self.schema_version != IDENTITY_ROLLBACK_VERSION:
            raise ValueError(f"unsupported rollback version: {self.schema_version}")
        if self.rollback_version != self.from_version + 1:
            raise ValueError("rollback must create a new profile version")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "rollback_id": self.rollback_id,
            "agent_id": self.agent_id,
            "application_id": self.application_id,
            "from_profile_ref": self.from_profile_ref,
            "restored_from_profile_ref": self.restored_from_profile_ref,
            "rollback_profile_ref": self.rollback_profile_ref,
            "from_version": self.from_version,
            "rollback_version": self.rollback_version,
            "reason": self.reason,
            "rolled_back_at": self.rolled_back_at,
            "rolled_back_by": self.rolled_back_by,
            "metadata": dict(self.metadata),
        }


def proposal_digest(proposal: IdentityUpdateProposal) -> str:
    return _digest(proposal.to_dict())


def decide_identity_update_proposal(
    proposal: IdentityUpdateProposal,
    *,
    proposer_actor: str,
    approver_actor: str,
    decision: ApprovalDecision,
    reason: str,
    decided_at: str,
    expires_at: Optional[str] = None,
    contradiction_refs: Sequence[str] = (),
    metadata: Optional[Mapping[str, Any]] = None,
) -> IdentityUpdateApproval:
    """Create an immutable approval decision bound to the exact proposal."""

    if proposal.applied:
        raise IdentityGovernanceError("already applied proposal cannot be decided again")
    if proposal.approval_state.value != "PENDING":
        raise IdentityGovernanceError("proposal is not pending approval")
    digest = proposal_digest(proposal)
    payload = {
        "proposal_id": proposal.proposal_id,
        "proposal_digest": digest,
        "proposer_actor": proposer_actor,
        "approver_actor": approver_actor,
        "decision": decision.value,
        "decided_at": decided_at,
        "contradiction_refs": tuple(contradiction_refs),
    }
    return IdentityUpdateApproval(
        approval_id="identity-approval:sha256:" + _digest(payload),
        proposal_id=proposal.proposal_id,
        proposal_digest=digest,
        proposer_actor=proposer_actor,
        approver_actor=approver_actor,
        decision=decision,
        reason=reason,
        decided_at=decided_at,
        expires_at=expires_at,
        contradiction_refs=tuple(str(item) for item in contradiction_refs),
        metadata=dict(metadata or {}),
    )


def invalidate_identity_approval(
    proposal: IdentityUpdateProposal,
    approval: IdentityUpdateApproval,
    *,
    contradiction_refs: Sequence[str],
    invalidated_at: str,
    invalidated_by: str,
    reason: str,
) -> IdentityUpdateApproval:
    """Invalidate a still-pending approved window when new evidence conflicts."""

    _require_approval_matches(proposal, approval)
    if approval.decision is not ApprovalDecision.APPROVE:
        raise IdentityGovernanceError("only an approval can be invalidated")
    if not contradiction_refs:
        raise IdentityGovernanceError("invalidation requires contradiction refs")
    return decide_identity_update_proposal(
        proposal,
        proposer_actor=approval.proposer_actor,
        approver_actor=invalidated_by,
        decision=ApprovalDecision.INVALIDATE,
        reason=reason,
        decided_at=invalidated_at,
        contradiction_refs=contradiction_refs,
        metadata={
            "invalidates_approval_ref": approval.approval_id,
            "previous_approver": approval.approver_actor,
        },
    )


def create_identity_profile_patch(
    proposal: IdentityUpdateProposal,
    approval: IdentityUpdateApproval,
    base_profile: IdentityProfile,
    *,
    changes: Sequence[IdentityPatchChange],
    created_at: str,
    created_by: str,
    now: str,
    metadata: Optional[Mapping[str, Any]] = None,
) -> IdentityProfilePatch:
    """Create a patch only from a valid, unexpired, exact approval."""

    _require_approval_matches(proposal, approval)
    if approval.decision is not ApprovalDecision.APPROVE:
        raise IdentityGovernanceError("identity patch requires APPROVE decision")
    if approval.expires_at is None or _instant(now) > _instant(approval.expires_at):
        raise IdentityGovernanceError("identity approval has expired")
    if not base_profile.active:
        raise IdentityGovernanceError("patch base profile must be active")
    patch_payload = {
        "proposal_id": proposal.proposal_id,
        "proposal_digest": approval.proposal_digest,
        "approval_id": approval.approval_id,
        "agent_id": base_profile.agent_id,
        "base_profile_ref": base_profile.profile_ref,
        "changes": [change.to_dict() for change in changes],
    }
    return IdentityProfilePatch(
        patch_id="identity-patch:sha256:" + _digest(patch_payload),
        proposal_id=proposal.proposal_id,
        proposal_digest=approval.proposal_digest,
        approval_id=approval.approval_id,
        agent_id=base_profile.agent_id,
        base_profile_ref=base_profile.profile_ref,
        base_profile_version=base_profile.version,
        changes=tuple(changes),
        created_at=created_at,
        created_by=created_by,
        metadata=dict(metadata or {}),
    )


def commit_identity_profile_patch(
    patch: IdentityProfilePatch,
    *,
    committed_at: str,
    committed_by: str,
    durable_ref: str,
) -> IdentityPatchCommit:
    """Create the durable commit record required before activation."""

    payload = {
        "patch_id": patch.patch_id,
        "patch_digest": patch.patch_digest,
        "durable_ref": durable_ref,
    }
    return IdentityPatchCommit(
        commit_id="identity-patch-commit:sha256:" + _digest(payload),
        patch_id=patch.patch_id,
        patch_digest=patch.patch_digest,
        committed_at=committed_at,
        committed_by=committed_by,
        durable_ref=durable_ref,
        metadata={"commit_before_activation": True},
    )


def activate_identity_profile_patch(
    proposal: IdentityUpdateProposal,
    approval: IdentityUpdateApproval,
    patch: IdentityProfilePatch,
    commit: IdentityPatchCommit,
    base_profile: IdentityProfile,
    *,
    activated_at: str,
    activated_by: str,
    existing_application_refs: Sequence[str] = (),
) -> tuple[IdentityProfile, IdentityApplicationRecord]:
    """Activate a committed patch exactly once and produce a new profile version."""

    _require_approval_matches(proposal, approval)
    if approval.decision is not ApprovalDecision.APPROVE:
        raise IdentityGovernanceError("profile activation requires APPROVE decision")
    if approval.expires_at is None or _instant(activated_at) > _instant(
        approval.expires_at
    ):
        raise IdentityGovernanceError("identity approval expired before activation")
    if patch.proposal_id != proposal.proposal_id:
        raise IdentityGovernanceError("patch proposal does not match")
    if patch.proposal_digest != approval.proposal_digest:
        raise IdentityGovernanceError("patch proposal digest does not match approval")
    if patch.approval_id != approval.approval_id:
        raise IdentityGovernanceError("patch approval does not match")
    if patch.agent_id != base_profile.agent_id:
        raise IdentityGovernanceError("patch agent does not match profile")
    if patch.base_profile_ref != base_profile.profile_ref:
        raise IdentityGovernanceError("patch base profile ref does not match")
    if patch.base_profile_version != base_profile.version:
        raise IdentityGovernanceError("patch base profile version does not match")
    if commit.patch_id != patch.patch_id or commit.patch_digest != patch.patch_digest:
        raise IdentityGovernanceError("durable commit does not match patch")

    application_payload = {
        "proposal_id": proposal.proposal_id,
        "approval_id": approval.approval_id,
        "patch_id": patch.patch_id,
        "patch_digest": patch.patch_digest,
        "commit_id": commit.commit_id,
        "base_profile_ref": base_profile.profile_ref,
        "activated_at": activated_at,
    }
    application_id = "identity-application:sha256:" + _digest(application_payload)
    if application_id in set(existing_application_refs):
        raise IdentityAlreadyAppliedError(
            "replay must not reapply an existing identity application"
        )

    next_traits = dict(base_profile.traits)
    for change in patch.changes:
        if change.operation is PatchOperation.SET:
            next_traits[change.key] = change.value
        else:
            next_traits.pop(change.key, None)

    provisional_profile = IdentityProfile(
        profile_id=f"{base_profile.agent_id}:v{base_profile.version + 1}",
        agent_id=base_profile.agent_id,
        version=base_profile.version + 1,
        traits=next_traits,
        created_at=activated_at,
        previous_profile_ref=base_profile.profile_ref,
        source_application_ref=application_id,
        active=True,
        metadata={
            "proposal_ref": proposal.proposal_id,
            "approval_ref": approval.approval_id,
            "patch_ref": patch.patch_id,
            "commit_ref": commit.commit_id,
        },
    )
    application = IdentityApplicationRecord(
        application_id=application_id,
        proposal_id=proposal.proposal_id,
        approval_id=approval.approval_id,
        patch_id=patch.patch_id,
        patch_digest=patch.patch_digest,
        commit_id=commit.commit_id,
        agent_id=base_profile.agent_id,
        previous_profile_ref=base_profile.profile_ref,
        new_profile_ref=provisional_profile.profile_ref,
        previous_version=base_profile.version,
        new_version=provisional_profile.version,
        activated_at=activated_at,
        activated_by=activated_by,
        metadata={"activation_after_commit": True},
    )
    return provisional_profile, application


def rollback_identity_application(
    current_profile: IdentityProfile,
    previous_profile: IdentityProfile,
    application: IdentityApplicationRecord,
    *,
    reason: str,
    rolled_back_at: str,
    rolled_back_by: str,
) -> tuple[IdentityProfile, IdentityRollbackRecord]:
    """Restore prior traits by creating a new version; never delete history."""

    if current_profile.profile_ref != application.new_profile_ref:
        raise IdentityGovernanceError("current profile does not match application")
    if previous_profile.profile_ref != application.previous_profile_ref:
        raise IdentityGovernanceError("rollback source does not match application")
    if current_profile.agent_id != previous_profile.agent_id:
        raise IdentityGovernanceError("rollback profiles belong to different agents")

    rollback_payload = {
        "application_id": application.application_id,
        "from_profile_ref": current_profile.profile_ref,
        "restored_from_profile_ref": previous_profile.profile_ref,
        "rolled_back_at": rolled_back_at,
    }
    rollback_id = "identity-rollback:sha256:" + _digest(rollback_payload)
    rollback_profile = IdentityProfile(
        profile_id=f"{current_profile.agent_id}:v{current_profile.version + 1}",
        agent_id=current_profile.agent_id,
        version=current_profile.version + 1,
        traits=dict(previous_profile.traits),
        created_at=rolled_back_at,
        previous_profile_ref=current_profile.profile_ref,
        source_application_ref=rollback_id,
        active=True,
        metadata={
            "rollback_of_application": application.application_id,
            "restored_from_profile_ref": previous_profile.profile_ref,
        },
    )
    record = IdentityRollbackRecord(
        rollback_id=rollback_id,
        agent_id=current_profile.agent_id,
        application_id=application.application_id,
        from_profile_ref=current_profile.profile_ref,
        restored_from_profile_ref=previous_profile.profile_ref,
        rollback_profile_ref=rollback_profile.profile_ref,
        from_version=current_profile.version,
        rollback_version=rollback_profile.version,
        reason=reason,
        rolled_back_at=rolled_back_at,
        rolled_back_by=rolled_back_by,
        metadata={"history_deleted": False},
    )
    return rollback_profile, record


def _require_approval_matches(
    proposal: IdentityUpdateProposal,
    approval: IdentityUpdateApproval,
) -> None:
    if approval.proposal_id != proposal.proposal_id:
        raise IdentityGovernanceError("approval proposal ID does not match")
    if approval.proposal_digest != proposal_digest(proposal):
        raise IdentityGovernanceError("approval is not bound to the exact proposal")


def _instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
