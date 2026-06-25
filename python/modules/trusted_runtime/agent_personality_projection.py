"""Read-only runtime projection of governed agent identity.

An AgentPersonalityProjection expresses approved identity and current bounded
capability state for a runtime consumer. It is not an identity source, cannot
approve or apply identity changes, and never grants tool or execution authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .capabilities_constraints_track_center import CapabilityConstraintResult
from .capability_contract import (
    CapabilityEventType,
    CapabilityStatus,
    ConstraintKind,
)
from .continuity_coordinator import ContinuityDecision
from .identity_governance import IdentityProfile


PERSONALITY_PROJECTION_VERSION = "trusted_runtime.agent_personality_projection.v0.1"
PERSONALITY_VALIDATION_VERSION = "trusted_runtime.personality_projection_validation.v0.1"
PERSONALITY_PROJECTION_POLICY_VERSION = "agent_personality_projection.v0.1"


class ProjectionScopeLevel(str, Enum):
    INDIVIDUAL = "individual"
    RELATIONSHIP = "relationship"
    PROJECT = "project"
    ORGANIZATION = "organization"
    SYSTEM = "system"


class ProjectionCategory(str, Enum):
    COMMUNICATION_STYLE = "communication_style"
    WORKING_TENDENCY = "working_tendency"
    RELATIONSHIP_RULE = "relationship_rule"
    CAPABILITY_CLAIM = "capability_claim"
    ACTIVE_CONSTRAINT = "active_constraint"


class ProjectionValidity(str, Enum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


_ALLOWED_TRAIT_PREFIXES = {
    "communication_style.": ProjectionCategory.COMMUNICATION_STYLE,
    "working_tendencies.": ProjectionCategory.WORKING_TENDENCY,
    "relationship_rules.": ProjectionCategory.RELATIONSHIP_RULE,
}


@dataclass(frozen=True)
class ProjectionScope:
    level: ProjectionScopeLevel
    counterparty_ref: Optional[str] = None
    project_ref: Optional[str] = None
    organization_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if self.level is ProjectionScopeLevel.RELATIONSHIP and not self.counterparty_ref:
            raise ValueError("relationship projection requires counterparty_ref")
        if self.level is ProjectionScopeLevel.PROJECT and not self.project_ref:
            raise ValueError("project projection requires project_ref")
        if self.level is ProjectionScopeLevel.ORGANIZATION and not self.organization_ref:
            raise ValueError("organization projection requires organization_ref")
        if self.level is not ProjectionScopeLevel.RELATIONSHIP and self.counterparty_ref:
            raise ValueError("counterparty_ref is only valid for relationship scope")
        if self.level is not ProjectionScopeLevel.PROJECT and self.project_ref:
            raise ValueError("project_ref is only valid for project scope")
        if self.level is not ProjectionScopeLevel.ORGANIZATION and self.organization_ref:
            raise ValueError("organization_ref is only valid for organization scope")

    @property
    def scope_ref(self) -> str:
        if self.level is ProjectionScopeLevel.RELATIONSHIP:
            return self.counterparty_ref or ""
        if self.level is ProjectionScopeLevel.PROJECT:
            return self.project_ref or ""
        if self.level is ProjectionScopeLevel.ORGANIZATION:
            return self.organization_ref or ""
        return self.level.value

    def to_dict(self) -> dict[str, Optional[str]]:
        return {
            "level": self.level.value,
            "counterparty_ref": self.counterparty_ref,
            "project_ref": self.project_ref,
            "organization_ref": self.organization_ref,
        }


@dataclass(frozen=True)
class ProjectedPersonalityItem:
    category: ProjectionCategory
    key: str
    value: Any
    source_refs: tuple[str, ...]
    source_scope: ProjectionScope
    status: str
    confidence: Optional[float] = None
    context_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key or not self.status:
            raise ValueError("projected personality item fields must not be empty")
        if not self.source_refs:
            raise ValueError("projected personality item requires provenance")
        _require_unique("projected source_refs", self.source_refs)
        _require_unique("projected context_refs", self.context_refs)
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("projected confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "key": self.key,
            "value": self.value,
            "source_refs": list(self.source_refs),
            "source_scope": self.source_scope.to_dict(),
            "status": self.status,
            "confidence": self.confidence,
            "context_refs": list(self.context_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AgentPersonalityProjection:
    projection_id: str
    agent_id: str
    identity_profile_ref: str
    identity_profile_version: int
    created_at: str
    scope: ProjectionScope
    communication_style: tuple[ProjectedPersonalityItem, ...]
    working_tendencies: tuple[ProjectedPersonalityItem, ...]
    relationship_rules: tuple[ProjectedPersonalityItem, ...]
    capability_claims: tuple[ProjectedPersonalityItem, ...]
    active_constraints: tuple[ProjectedPersonalityItem, ...]
    source_refs: tuple[str, ...]
    excluded_or_disputed_refs: tuple[str, ...]
    expires_at: Optional[str] = None
    validity: ProjectionValidity = ProjectionValidity.ACTIVE
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = PERSONALITY_PROJECTION_POLICY_VERSION
    schema_version: str = PERSONALITY_PROJECTION_VERSION

    def __post_init__(self) -> None:
        required = (
            self.projection_id,
            self.agent_id,
            self.identity_profile_ref,
            self.created_at,
            self.policy_version,
        )
        if not all(required):
            raise ValueError("personality projection fields must not be empty")
        if self.schema_version != PERSONALITY_PROJECTION_VERSION:
            raise ValueError(f"unsupported personality projection: {self.schema_version}")
        if self.identity_profile_version < 1:
            raise ValueError("identity profile version must be positive")
        if self.validity is not ProjectionValidity.ACTIVE:
            raise ValueError("new personality projection must start ACTIVE")
        if self.expires_at is not None:
            if _instant(self.expires_at) <= _instant(self.created_at):
                raise ValueError("projection expiry must be after creation")
        _require_unique("projection source_refs", self.source_refs)
        _require_unique(
            "projection excluded_or_disputed_refs",
            self.excluded_or_disputed_refs,
        )
        if self.identity_profile_ref not in self.source_refs:
            raise ValueError("projection source refs must include identity profile")
        for item in self.all_items:
            if not _scope_allows(self.scope, item.source_scope):
                raise ValueError("projected item exceeds requested runtime scope")

    @property
    def all_items(self) -> tuple[ProjectedPersonalityItem, ...]:
        return (
            *self.communication_style,
            *self.working_tendencies,
            *self.relationship_rules,
            *self.capability_claims,
            *self.active_constraints,
        )

    @property
    def projection_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projection_id": self.projection_id,
            "agent_id": self.agent_id,
            "identity_profile_ref": self.identity_profile_ref,
            "identity_profile_version": self.identity_profile_version,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "validity": self.validity.value,
            "scope": self.scope.to_dict(),
            "communication_style": [item.to_dict() for item in self.communication_style],
            "working_tendencies": [item.to_dict() for item in self.working_tendencies],
            "relationship_rules": [item.to_dict() for item in self.relationship_rules],
            "capability_claims": [item.to_dict() for item in self.capability_claims],
            "active_constraints": [item.to_dict() for item in self.active_constraints],
            "source_refs": list(self.source_refs),
            "excluded_or_disputed_refs": list(self.excluded_or_disputed_refs),
            "authority_effects": {
                "may_authorize_execution": False,
                "may_approve_identity_change": False,
                "may_apply_identity_change": False,
                "may_create_profile_patch": False,
                "may_grant_tool_access": False,
                "may_deny_tool_access": False,
                "may_bypass_governance": False,
                "may_expand_scope": False,
            },
            "policy_version": self.policy_version,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PersonalityProjectionValidation:
    validation_id: str
    projection_id: str
    projection_digest: str
    evaluated_at: str
    validity: ProjectionValidity
    reason_codes: tuple[str, ...]
    active_identity_profile_ref: str
    revoked_source_refs: tuple[str, ...]
    schema_version: str = PERSONALITY_VALIDATION_VERSION

    def __post_init__(self) -> None:
        if not all(
            (
                self.validation_id,
                self.projection_id,
                self.projection_digest,
                self.evaluated_at,
                self.active_identity_profile_ref,
            )
        ):
            raise ValueError("projection validation fields must not be empty")
        if self.schema_version != PERSONALITY_VALIDATION_VERSION:
            raise ValueError(f"unsupported projection validation: {self.schema_version}")
        if not self.reason_codes:
            raise ValueError("projection validation requires a reason code")
        _require_unique("projection validation reasons", self.reason_codes)
        _require_unique("revoked source refs", self.revoked_source_refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "validation_id": self.validation_id,
            "projection_id": self.projection_id,
            "projection_digest": self.projection_digest,
            "evaluated_at": self.evaluated_at,
            "validity": self.validity.value,
            "reason_codes": list(self.reason_codes),
            "active_identity_profile_ref": self.active_identity_profile_ref,
            "revoked_source_refs": list(self.revoked_source_refs),
            "projection_mutation_allowed": False,
            "identity_mutation_allowed": False,
            "execution_authorized": False,
        }


def project_agent_personality(
    profile: IdentityProfile,
    *,
    scope: ProjectionScope,
    created_at: str,
    capability_results: Sequence[CapabilityConstraintResult] = (),
    expires_at: Optional[str] = None,
) -> AgentPersonalityProjection:
    """Create a deterministic, read-only runtime projection.

    Only an active, governance-backed profile is accepted. Profile traits are
    projected from explicit supported namespaces. Current capability and
    limitation claims are included only when the capability center accepted a
    source-backed bounded observation in the requested context.
    """

    _instant(created_at)
    if not profile.active:
        raise ValueError("inactive identity profile cannot be projected")
    profile_source_refs = _governed_profile_refs(profile)

    buckets: dict[ProjectionCategory, list[ProjectedPersonalityItem]] = {
        category: [] for category in ProjectionCategory
    }
    excluded: list[str] = []

    for trait_key in sorted(profile.traits):
        category, projected_key = _trait_category(trait_key)
        if category is None:
            excluded.append(f"trait:{trait_key}:unsupported_namespace")
            continue
        item, reason = _project_trait(
            trait_key=trait_key,
            projected_key=projected_key,
            category=category,
            raw_value=profile.traits[trait_key],
            projection_scope=scope,
            created_at=created_at,
            profile_source_refs=profile_source_refs,
        )
        if item is None:
            excluded.append(f"trait:{trait_key}:{reason}")
            continue
        buckets[category].append(item)

    capability_items, capability_excluded = _project_capability_results(
        capability_results,
        projection_scope=scope,
    )
    excluded.extend(capability_excluded)
    for item in capability_items:
        buckets[item.category].append(item)

    for category in buckets:
        buckets[category] = sorted(
            buckets[category],
            key=lambda item: (item.key, _canonical_json(item.value), item.status),
        )

    all_items = tuple(
        item
        for category in ProjectionCategory
        for item in buckets[category]
    )
    source_refs = _unique(
        (
            *profile_source_refs,
            *(ref for item in all_items for ref in item.source_refs),
        )
    )
    excluded_refs = tuple(sorted(set(excluded)))
    payload = {
        "agent_id": profile.agent_id,
        "identity_profile_ref": profile.profile_ref,
        "identity_profile_version": profile.version,
        "created_at": created_at,
        "expires_at": expires_at,
        "scope": scope.to_dict(),
        "items": [item.to_dict() for item in all_items],
        "excluded_or_disputed_refs": list(excluded_refs),
        "policy_version": PERSONALITY_PROJECTION_POLICY_VERSION,
    }
    projection_id = "agent-personality-projection:sha256:" + _digest(payload)

    return AgentPersonalityProjection(
        projection_id=projection_id,
        agent_id=profile.agent_id,
        identity_profile_ref=profile.profile_ref,
        identity_profile_version=profile.version,
        created_at=created_at,
        expires_at=expires_at,
        scope=scope,
        communication_style=tuple(
            buckets[ProjectionCategory.COMMUNICATION_STYLE]
        ),
        working_tendencies=tuple(
            buckets[ProjectionCategory.WORKING_TENDENCY]
        ),
        relationship_rules=tuple(
            buckets[ProjectionCategory.RELATIONSHIP_RULE]
        ),
        capability_claims=tuple(
            buckets[ProjectionCategory.CAPABILITY_CLAIM]
        ),
        active_constraints=tuple(
            buckets[ProjectionCategory.ACTIVE_CONSTRAINT]
        ),
        source_refs=source_refs,
        excluded_or_disputed_refs=excluded_refs,
        metadata={
            "projection_is_read_only": True,
            "profile_must_be_governed_and_active": True,
            "unsupported_or_disputed_items_are_excluded": True,
            "capability_claims_require_accepted_current_claims": True,
            "prompt_adapter_is_not_identity_source": True,
        },
    )


def validate_personality_projection(
    projection: AgentPersonalityProjection,
    *,
    active_profile: IdentityProfile,
    evaluated_at: str,
    revoked_source_refs: Sequence[str] = (),
) -> PersonalityProjectionValidation:
    """Validate freshness without modifying the projection or identity profile."""

    evaluation_time = _instant(evaluated_at)
    revoked = tuple(sorted(set(str(ref) for ref in revoked_source_refs if ref)))
    reasons: list[str] = []

    if projection.agent_id != active_profile.agent_id:
        validity = ProjectionValidity.STALE
        reasons.append("AGENT_ID_MISMATCH")
    elif any(ref in projection.source_refs for ref in revoked):
        validity = ProjectionValidity.REVOKED
        reasons.append("SOURCE_REVOKED")
    elif not active_profile.active:
        validity = ProjectionValidity.STALE
        reasons.append("ACTIVE_PROFILE_INACTIVE")
    elif active_profile.profile_ref != projection.identity_profile_ref:
        validity = ProjectionValidity.STALE
        reasons.append("IDENTITY_PROFILE_SUPERSEDED_OR_ROLLED_BACK")
    elif (
        projection.expires_at is not None
        and _instant(projection.expires_at) <= evaluation_time
    ):
        validity = ProjectionValidity.EXPIRED
        reasons.append("PROJECTION_EXPIRED")
    else:
        validity = ProjectionValidity.ACTIVE
        reasons.append("PROJECTION_CURRENT")

    payload = {
        "projection_id": projection.projection_id,
        "projection_digest": projection.projection_digest,
        "active_identity_profile_ref": active_profile.profile_ref,
        "evaluated_at": evaluated_at,
        "validity": validity.value,
        "reason_codes": reasons,
        "revoked_source_refs": revoked,
    }
    return PersonalityProjectionValidation(
        validation_id="personality-projection-validation:sha256:" + _digest(payload),
        projection_id=projection.projection_id,
        projection_digest=projection.projection_digest,
        evaluated_at=evaluated_at,
        validity=validity,
        reason_codes=tuple(reasons),
        active_identity_profile_ref=active_profile.profile_ref,
        revoked_source_refs=revoked,
    )


def render_personality_projection_markdown(
    projection: AgentPersonalityProjection,
) -> str:
    """Render bounded runtime guidance for AGENTS.md or CLAUDE.md consumption."""

    lines = [
        "# Governed Agent Personality Projection",
        "",
        f"- Agent: `{projection.agent_id}`",
        f"- Identity profile: `{projection.identity_profile_ref}`",
        f"- Identity version: `{projection.identity_profile_version}`",
        f"- Projection: `{projection.projection_id}`",
        f"- Scope: `{projection.scope.level.value}:{projection.scope.scope_ref}`",
        "",
        "> This is read-only behavioral guidance derived from governed identity. ",
        "> It does not grant tool access, execution authority, approval authority, ",
        "> policy bypass, or permission to rewrite identity.",
    ]
    _render_items(lines, "Communication style", projection.communication_style)
    _render_items(lines, "Working tendencies", projection.working_tendencies)
    _render_items(lines, "Relationship rules", projection.relationship_rules)
    _render_items(lines, "Current capability claims", projection.capability_claims)
    _render_items(lines, "Active contextual constraints", projection.active_constraints)
    if projection.excluded_or_disputed_refs:
        lines.extend(
            [
                "",
                "## Excluded or disputed inputs",
                "",
                *(
                    f"- `{ref}`"
                    for ref in projection.excluded_or_disputed_refs
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- Execution authorization: **false**",
            "- Tool access grant or denial: **false**",
            "- Identity approval or application: **false**",
            "- Governance bypass: **false**",
            "- Scope expansion: **false**",
            "",
        ]
    )
    return "\n".join(lines)


def _project_trait(
    *,
    trait_key: str,
    projected_key: str,
    category: ProjectionCategory,
    raw_value: Any,
    projection_scope: ProjectionScope,
    created_at: str,
    profile_source_refs: tuple[str, ...],
) -> tuple[Optional[ProjectedPersonalityItem], str]:
    state = "ACTIVE"
    disputed = False
    conflict_refs: tuple[str, ...] = ()
    expires_at: Optional[str] = None
    confidence: Optional[float] = None
    source_scope = ProjectionScope(ProjectionScopeLevel.INDIVIDUAL)
    trait_source_refs: tuple[str, ...] = ()
    value = raw_value

    if isinstance(raw_value, Mapping):
        if "value" not in raw_value:
            return None, "missing_value"
        value = raw_value["value"]
        state = str(raw_value.get("state", "ACTIVE"))
        disputed = bool(raw_value.get("disputed", False))
        expires_raw = raw_value.get("expires_at")
        expires_at = str(expires_raw) if expires_raw is not None else None
        confidence_raw = raw_value.get("confidence")
        confidence = (
            float(confidence_raw) if confidence_raw is not None else None
        )
        source_scope = _scope_from_mapping(raw_value.get("scope"))
        refs_raw = raw_value.get("source_refs", ())
        trait_source_refs = _string_sequence(refs_raw, "trait source_refs")
        conflict_refs = _string_sequence(
            raw_value.get("conflict_refs", ()),
            "trait conflict_refs",
        )

    if state != "ACTIVE":
        return None, f"state_{state.lower()}"
    if disputed or conflict_refs:
        return None, "disputed_or_conflicting"
    if expires_at is not None and _instant(expires_at) <= _instant(created_at):
        return None, "expired"
    if not _scope_allows(projection_scope, source_scope):
        return None, "scope_mismatch"
    if category is ProjectionCategory.RELATIONSHIP_RULE:
        if source_scope.level is not ProjectionScopeLevel.RELATIONSHIP:
            return None, "relationship_rule_not_relationship_scoped"
    refs = _unique((*profile_source_refs, *trait_source_refs))
    return (
        ProjectedPersonalityItem(
            category=category,
            key=projected_key,
            value=value,
            source_refs=refs,
            source_scope=source_scope,
            status="ACTIVE",
            confidence=confidence,
            metadata={
                "identity_trait_key": trait_key,
                "source_state": state,
                "projection_does_not_mutate_identity": True,
            },
        ),
        "",
    )


def _project_capability_results(
    results: Sequence[CapabilityConstraintResult],
    *,
    projection_scope: ProjectionScope,
) -> tuple[tuple[ProjectedPersonalityItem, ...], tuple[str, ...]]:
    items: dict[tuple[ProjectionCategory, str], ProjectedPersonalityItem] = {}
    excluded: list[str] = []

    for result in sorted(results, key=lambda value: value.result_id):
        event = result.event
        exclusion_ref = f"capability-result:{result.result_id}"
        if result.assessment.decision is not ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION:
            excluded.append(f"{exclusion_ref}:not_accepted")
            continue
        if event.event_type not in {
            CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
            CapabilityEventType.CURRENT_LIMITATION_CLAIM,
        }:
            excluded.append(f"{exclusion_ref}:not_current_claim")
            continue
        if not event.evidence_refs:
            excluded.append(f"{exclusion_ref}:missing_evidence")
            continue
        if not _capability_context_matches(projection_scope, event.context_refs):
            excluded.append(f"{exclusion_ref}:context_mismatch")
            continue

        if event.event_type is CapabilityEventType.CURRENT_CAPABILITY_CLAIM:
            if event.capability_status not in {
                CapabilityStatus.AVAILABLE,
                CapabilityStatus.RECOVERED,
            }:
                excluded.append(f"{exclusion_ref}:capability_not_current")
                continue
            category = ProjectionCategory.CAPABILITY_CLAIM
        else:
            if event.capability_status not in {
                CapabilityStatus.CONSTRAINED,
                CapabilityStatus.UNAVAILABLE,
            } or event.constraint_kind in {
                ConstraintKind.NONE,
                ConstraintKind.UNKNOWN,
            }:
                excluded.append(f"{exclusion_ref}:constraint_not_current")
                continue
            category = ProjectionCategory.ACTIVE_CONSTRAINT

        source_refs = _unique(
            (
                result.result_id,
                event.event_id,
                result.observation.observation_id,
                result.assessment.assessment_id,
                *event.evidence_refs,
            )
        )
        item = ProjectedPersonalityItem(
            category=category,
            key=event.capability_id,
            value=event.statement,
            source_refs=source_refs,
            source_scope=projection_scope,
            status=event.capability_status.value,
            confidence=event.confidence,
            context_refs=event.context_refs,
            metadata={
                "constraint_kind": event.constraint_kind.value,
                "capability_event_type": event.event_type.value,
                "observer_refs": list(event.observer_refs),
                "capability_result_ref": result.result_id,
                "capability_description_is_not_permission": True,
            },
        )
        key = (category, event.capability_id)
        existing = items.get(key)
        if existing is None:
            items[key] = item
            continue
        if (
            existing.value != item.value
            or existing.status != item.status
            or existing.context_refs != item.context_refs
        ):
            del items[key]
            excluded.extend(
                (
                    f"capability:{event.capability_id}:conflicting_current_claim",
                    f"{exclusion_ref}:conflicting_current_claim",
                )
            )
            continue
        items[key] = ProjectedPersonalityItem(
            category=existing.category,
            key=existing.key,
            value=existing.value,
            source_refs=_unique((*existing.source_refs, *item.source_refs)),
            source_scope=existing.source_scope,
            status=existing.status,
            confidence=max(
                value
                for value in (existing.confidence, item.confidence)
                if value is not None
            ),
            context_refs=_unique((*existing.context_refs, *item.context_refs)),
            metadata=existing.metadata,
        )

    return (
        tuple(sorted(items.values(), key=lambda item: (item.category.value, item.key))),
        tuple(sorted(set(excluded))),
    )


def _governed_profile_refs(profile: IdentityProfile) -> tuple[str, ...]:
    metadata_refs = _string_sequence(
        profile.metadata.get("source_refs", ()),
        "profile metadata source_refs",
    )
    approved_baseline = (
        profile.version == 1
        and profile.metadata.get("governance_status") == "APPROVED_BASELINE"
        and bool(metadata_refs)
    )
    if not profile.source_application_ref and not approved_baseline:
        raise ValueError(
            "identity profile requires a governed application or approved baseline"
        )
    return _unique(
        (
            profile.profile_ref,
            profile.source_application_ref or "",
            *metadata_refs,
        )
    )


def _trait_category(
    trait_key: str,
) -> tuple[Optional[ProjectionCategory], str]:
    for prefix, category in _ALLOWED_TRAIT_PREFIXES.items():
        if trait_key.startswith(prefix) and len(trait_key) > len(prefix):
            return category, trait_key[len(prefix) :]
    return None, trait_key


def _scope_from_mapping(raw: Any) -> ProjectionScope:
    if raw is None:
        return ProjectionScope(ProjectionScopeLevel.INDIVIDUAL)
    if isinstance(raw, str):
        return ProjectionScope(ProjectionScopeLevel(raw))
    if not isinstance(raw, Mapping):
        raise ValueError("trait scope must be a string or mapping")
    return ProjectionScope(
        level=ProjectionScopeLevel(str(raw["level"])),
        counterparty_ref=_optional_string(raw.get("counterparty_ref")),
        project_ref=_optional_string(raw.get("project_ref")),
        organization_ref=_optional_string(raw.get("organization_ref")),
    )


def _scope_allows(target: ProjectionScope, source: ProjectionScope) -> bool:
    if source.level is ProjectionScopeLevel.INDIVIDUAL:
        return True
    if source.level is not target.level:
        return False
    if source.level is ProjectionScopeLevel.RELATIONSHIP:
        return source.counterparty_ref == target.counterparty_ref
    if source.level is ProjectionScopeLevel.PROJECT:
        return source.project_ref == target.project_ref
    if source.level is ProjectionScopeLevel.ORGANIZATION:
        return source.organization_ref == target.organization_ref
    return source.level is ProjectionScopeLevel.SYSTEM


def _capability_context_matches(
    scope: ProjectionScope,
    context_refs: tuple[str, ...],
) -> bool:
    if scope.level is ProjectionScopeLevel.INDIVIDUAL:
        return False
    if scope.level is ProjectionScopeLevel.SYSTEM:
        return False
    return scope.scope_ref in context_refs


def _render_items(
    lines: list[str],
    title: str,
    items: tuple[ProjectedPersonalityItem, ...],
) -> None:
    if not items:
        return
    lines.extend(("", f"## {title}", ""))
    for item in items:
        value = json.dumps(item.value, sort_keys=True, ensure_ascii=False)
        refs = ", ".join(f"`{ref}`" for ref in item.source_refs)
        lines.append(
            f"- **{item.key}** = `{value}`; status `{item.status}`; sources: {refs}"
        )


def _string_sequence(raw: Any, name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    values = tuple(str(value) for value in raw if value)
    _require_unique(name, values)
    return values


def _optional_string(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid RFC3339 timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone {value!r}")
    return parsed.astimezone(timezone.utc)


def _require_unique(name: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


__all__ = [
    "AgentPersonalityProjection",
    "PersonalityProjectionValidation",
    "ProjectedPersonalityItem",
    "ProjectionCategory",
    "ProjectionScope",
    "ProjectionScopeLevel",
    "ProjectionValidity",
    "project_agent_personality",
    "render_personality_projection_markdown",
    "validate_personality_projection",
]
