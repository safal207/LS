"""Governed aggregation for VerifiedEpisode v0.2 records.

The v0.2 path preserves supporting, failure, and contradicting evidence as
separate roles. It is intentionally versioned beside the v0.1 aggregator so
existing callers keep their current behavior.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from statistics import mean
from typing import Any, Mapping, Optional, Sequence

from .identity_learning import (
    AggregationStatus,
    IDENTITY_PROPOSAL_POLICY_VERSION,
    IdentityLearningConsistencyError,
    IdentityUpdateProposal,
)


VERIFIED_EPISODE_V02_VERSION = "trusted_runtime.verified_episode.v0.2"
LESSON_AGGREGATION_V02_VERSION = "trusted_runtime.lesson_aggregation.v0.2"


class EvidenceRoleV02(str, Enum):
    SUPPORTING = "supporting"
    FAILURE = "failure"
    CONTRADICTING = "contradicting"


_OUTCOME_ROLE = {
    "expected": EvidenceRoleV02.SUPPORTING,
    "failed": EvidenceRoleV02.FAILURE,
    "unexpected": EvidenceRoleV02.CONTRADICTING,
}


@dataclass(frozen=True)
class VerifiedEpisodeV02View:
    """Minimal immutable projection required by the v0.2 aggregator."""

    episode_id: str
    causal_trace_id: str
    created_at: str
    scope: str
    repeat_key: str
    statement: str
    confidence: float
    outcome_class: str
    evidence_role: EvidenceRoleV02
    expires_at: Optional[str]
    supersedes_episode_id: Optional[str]
    evidence_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    payload_digest: str
    schema_version: str = VERIFIED_EPISODE_V02_VERSION

    def __post_init__(self) -> None:
        required = (
            self.episode_id,
            self.causal_trace_id,
            self.created_at,
            self.scope,
            self.repeat_key,
            self.statement,
            self.outcome_class,
            self.payload_digest,
        )
        if not all(required):
            raise ValueError("v0.2 aggregation episode fields must not be empty")
        if self.schema_version != VERIFIED_EPISODE_V02_VERSION:
            raise ValueError(
                f"unsupported v0.2 episode version: {self.schema_version}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("lesson confidence must be between 0 and 1")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("lesson evidence refs must be unique")
        if len(self.provenance_refs) != len(set(self.provenance_refs)):
            raise ValueError("provenance refs must be unique")
        if self.supersedes_episode_id == self.episode_id:
            raise IdentityLearningConsistencyError(
                "an episode cannot supersede itself"
            )
        expected_role = _OUTCOME_ROLE.get(self.outcome_class)
        if expected_role is None or self.evidence_role is not expected_role:
            raise IdentityLearningConsistencyError(
                "v0.2 outcome_class and lesson.evidence_role are inconsistent"
            )
        _instant(self.created_at)
        if self.expires_at is not None:
            _instant(self.expires_at)


@dataclass(frozen=True)
class LessonAggregationV02:
    """Inspectable v0.2 aggregation with failure evidence kept first-class."""

    aggregation_id: str
    scope: str
    repeat_key: str
    candidate_statement: str
    created_at: str
    status: AggregationStatus
    supporting_episode_refs: tuple[str, ...]
    failure_episode_refs: tuple[str, ...]
    contradicting_episode_refs: tuple[str, ...]
    ignored_episode_refs: tuple[str, ...]
    support_count: int
    failure_count: int
    contradiction_count: int
    ignored_count: int
    aggregated_confidence: float
    required_support_count: int
    proposal: Optional[IdentityUpdateProposal]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = LESSON_AGGREGATION_V02_VERSION

    def __post_init__(self) -> None:
        required = (
            self.aggregation_id,
            self.scope,
            self.repeat_key,
            self.candidate_statement,
            self.created_at,
        )
        if not all(required):
            raise ValueError("v0.2 lesson aggregation fields must not be empty")
        if self.schema_version != LESSON_AGGREGATION_V02_VERSION:
            raise ValueError(
                f"unsupported v0.2 aggregation version: {self.schema_version}"
            )
        if self.required_support_count < 3:
            raise ValueError("aggregation requires at least three support episodes")
        counts = (
            (self.support_count, self.supporting_episode_refs, "support"),
            (self.failure_count, self.failure_episode_refs, "failure"),
            (
                self.contradiction_count,
                self.contradicting_episode_refs,
                "contradiction",
            ),
            (self.ignored_count, self.ignored_episode_refs, "ignored"),
        )
        for count, refs, name in counts:
            if count != len(refs):
                raise ValueError(f"{name} count does not match refs")
        all_refs = (
            *self.supporting_episode_refs,
            *self.failure_episode_refs,
            *self.contradicting_episode_refs,
            *self.ignored_episode_refs,
        )
        if len(all_refs) != len(set(all_refs)):
            raise ValueError("an episode may appear in only one aggregation bucket")
        if not 0.0 <= self.aggregated_confidence <= 1.0:
            raise ValueError("aggregated confidence must be between 0 and 1")
        if self.status is AggregationStatus.READY_FOR_REVIEW:
            if self.proposal is None:
                raise ValueError("ready aggregation requires a proposal")
            if self.contradiction_count:
                raise ValueError("conflicted aggregation cannot be ready")
        elif self.proposal is not None:
            raise ValueError("non-ready aggregation cannot contain a proposal")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "aggregation_id": self.aggregation_id,
            "scope": self.scope,
            "repeat_key": self.repeat_key,
            "candidate_statement": self.candidate_statement,
            "created_at": self.created_at,
            "status": self.status.value,
            "supporting_episode_refs": list(self.supporting_episode_refs),
            "failure_episode_refs": list(self.failure_episode_refs),
            "contradicting_episode_refs": list(
                self.contradicting_episode_refs
            ),
            "ignored_episode_refs": list(self.ignored_episode_refs),
            "support_count": self.support_count,
            "failure_count": self.failure_count,
            "contradiction_count": self.contradiction_count,
            "ignored_count": self.ignored_count,
            "aggregated_confidence": self.aggregated_confidence,
            "required_support_count": self.required_support_count,
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "metadata": dict(self.metadata),
        }


def aggregate_verified_episode_v02_mappings(
    payloads: Sequence[Mapping[str, Any]],
    *,
    scope: str,
    repeat_key: str,
    candidate_statement: str,
    created_at: str,
    required_support_count: int = 3,
    metadata: Optional[Mapping[str, Any]] = None,
) -> LessonAggregationV02:
    """Aggregate VerifiedEpisode v0.2 mappings without trusting v0.1 projection.

    Only `supporting` episodes count toward the proposal threshold. Verified
    `failure` episodes remain first-class operational outcomes. Verified
    `contradicting` episodes lower confidence and block proposal creation.
    Expired and superseded episodes remain inspectable but do not count as
    current influence.
    """

    if not all((scope, repeat_key, candidate_statement, created_at)):
        raise ValueError("aggregation query fields must not be empty")
    if required_support_count < 3:
        raise ValueError("required_support_count must be at least three")
    evaluation_time = _instant(created_at)

    views = _validated_unique_views(payloads)
    superseded_ids = {
        item.supersedes_episode_id
        for item in views
        if item.supersedes_episode_id is not None
    }

    supporting: list[VerifiedEpisodeV02View] = []
    failures: list[VerifiedEpisodeV02View] = []
    contradicting: list[VerifiedEpisodeV02View] = []
    ignored: list[VerifiedEpisodeV02View] = []
    ignored_reasons: dict[str, str] = {}

    for item in views:
        reason: Optional[str] = None
        if item.scope != scope or item.repeat_key != repeat_key:
            reason = "scope_or_repeat_key_mismatch"
        elif item.episode_id in superseded_ids:
            reason = "superseded"
        elif (
            item.expires_at is not None
            and _instant(item.expires_at) <= evaluation_time
        ):
            reason = "expired"

        if reason is not None:
            ignored.append(item)
            ignored_reasons[item.episode_id] = reason
            continue

        if item.evidence_role is EvidenceRoleV02.FAILURE:
            failures.append(item)
            continue
        if item.evidence_role is EvidenceRoleV02.CONTRADICTING:
            contradicting.append(item)
            continue
        if _normalize(item.statement) == _normalize(candidate_statement):
            supporting.append(item)
        else:
            contradicting.append(item)

    support_confidence = (
        mean(item.confidence for item in supporting) if supporting else 0.0
    )
    contradiction_confidence = (
        mean(item.confidence for item in contradicting)
        if contradicting
        else 0.0
    )
    aggregated_confidence = round(
        max(0.0, min(1.0, support_confidence - 0.5 * contradiction_confidence)),
        6,
    )

    if not supporting and not failures and not contradicting:
        status = AggregationStatus.NO_ELIGIBLE_EPISODES
    elif contradicting:
        status = AggregationStatus.CONFLICTED
    elif len(supporting) < required_support_count:
        status = AggregationStatus.INSUFFICIENT_SUPPORT
    else:
        status = AggregationStatus.READY_FOR_REVIEW

    supporting_refs = tuple(item.episode_id for item in supporting)
    failure_refs = tuple(item.episode_id for item in failures)
    contradicting_refs = tuple(item.episode_id for item in contradicting)
    ignored_refs = tuple(item.episode_id for item in ignored)

    all_active = (*supporting, *failures, *contradicting)
    evidence_refs = _unique(
        tuple(
            ref
            for item in all_active
            for ref in (
                item.episode_id,
                item.causal_trace_id,
                *item.evidence_refs,
                *item.provenance_refs,
            )
        )
    )

    proposal: Optional[IdentityUpdateProposal] = None
    if status is AggregationStatus.READY_FOR_REVIEW:
        proposal_payload = {
            "scope": scope,
            "repeat_key": repeat_key,
            "candidate_statement": candidate_statement,
            "supporting_episode_refs": supporting_refs,
            "failure_episode_refs": failure_refs,
            "aggregated_confidence": aggregated_confidence,
            "policy_version": IDENTITY_PROPOSAL_POLICY_VERSION,
            "source_episode_schema_version": VERIFIED_EPISODE_V02_VERSION,
        }
        proposal = IdentityUpdateProposal(
            proposal_id="identity-proposal:sha256:"
            + hashlib.sha256(
                _canonical_json(proposal_payload).encode("utf-8")
            ).hexdigest(),
            scope=scope,
            repeat_key=repeat_key,
            candidate_statement=candidate_statement,
            created_at=created_at,
            aggregated_confidence=aggregated_confidence,
            support_count=len(supporting),
            required_support_count=required_support_count,
            supporting_episode_refs=supporting_refs,
            evidence_refs=evidence_refs,
            metadata={
                "operation": "CONSIDER_STABLE_IDENTITY_UPDATE",
                "application": "separate_governed_operation",
                "repetition_is_not_proof": True,
                "source_episode_schema_version": VERIFIED_EPISODE_V02_VERSION,
                "evidence_role_policy": {
                    "supporting": "counts_toward_threshold",
                    "failure": "preserved_not_counted",
                    "contradicting": "blocks_proposal",
                },
                "failure_episode_refs": list(failure_refs),
                "contradicting_episode_refs": [],
                "causal_trace_refs": [
                    item.causal_trace_id for item in (*supporting, *failures)
                ],
            },
        )

    aggregation_payload = {
        "scope": scope,
        "repeat_key": repeat_key,
        "candidate_statement": candidate_statement,
        "supporting_episode_refs": supporting_refs,
        "failure_episode_refs": failure_refs,
        "contradicting_episode_refs": contradicting_refs,
        "ignored_episode_refs": ignored_refs,
        "status": status.value,
        "required_support_count": required_support_count,
        "source_episode_schema_version": VERIFIED_EPISODE_V02_VERSION,
    }
    aggregation_metadata = dict(metadata or {})
    aggregation_metadata.setdefault(
        "source_episode_schema_version", VERIFIED_EPISODE_V02_VERSION
    )
    aggregation_metadata.setdefault(
        "evidence_role_policy",
        {
            "supporting": "counts_toward_threshold",
            "failure": "preserved_not_counted",
            "contradicting": "blocks_proposal",
        },
    )
    aggregation_metadata.setdefault("contradiction_policy", "BLOCK_PROPOSAL")
    aggregation_metadata.setdefault(
        "confidence_method", "mean_support_minus_conflict_penalty"
    )
    aggregation_metadata.setdefault("episodes_are_immutable", True)
    aggregation_metadata.setdefault("ignored_reasons", ignored_reasons)
    aggregation_metadata.setdefault(
        "v0_1_projection_is_not_v0_2_trust_status", True
    )

    return LessonAggregationV02(
        aggregation_id="lesson-aggregation-v0.2:sha256:"
        + hashlib.sha256(
            _canonical_json(aggregation_payload).encode("utf-8")
        ).hexdigest(),
        scope=scope,
        repeat_key=repeat_key,
        candidate_statement=candidate_statement,
        created_at=created_at,
        status=status,
        supporting_episode_refs=supporting_refs,
        failure_episode_refs=failure_refs,
        contradicting_episode_refs=contradicting_refs,
        ignored_episode_refs=ignored_refs,
        support_count=len(supporting),
        failure_count=len(failures),
        contradiction_count=len(contradicting),
        ignored_count=len(ignored),
        aggregated_confidence=aggregated_confidence,
        required_support_count=required_support_count,
        proposal=proposal,
        metadata=aggregation_metadata,
    )


def verified_episode_v02_view_from_mapping(
    payload: Mapping[str, Any],
) -> VerifiedEpisodeV02View:
    """Validate the aggregation-relevant fields of a v0.2 episode mapping."""

    schema_version = str(payload.get("schema_version", ""))
    if schema_version != VERIFIED_EPISODE_V02_VERSION:
        raise IdentityLearningConsistencyError(
            f"expected {VERIFIED_EPISODE_V02_VERSION}, got {schema_version!r}"
        )
    if payload.get("status") != "VERIFIED":
        raise IdentityLearningConsistencyError(
            "v0.2 aggregation accepts only VERIFIED episodes"
        )
    if payload.get("experience_eligible") is not True:
        raise IdentityLearningConsistencyError(
            "v0.2 episode is not experience eligible"
        )
    if payload.get("identity_update_eligible") is not False:
        raise IdentityLearningConsistencyError(
            "single v0.2 episode cannot be identity-update eligible"
        )

    identity_update = _mapping(payload, "identity_update")
    if identity_update.get("allowed") is not False:
        raise IdentityLearningConsistencyError(
            "single v0.2 episode cannot allow identity mutation"
        )
    if identity_update.get("applied") is not False:
        raise IdentityLearningConsistencyError(
            "single v0.2 episode cannot apply identity mutation"
        )

    lesson = _mapping(payload, "lesson")
    lifecycle = _mapping(payload, "lifecycle")
    provenance = _mapping(payload, "provenance")
    role = EvidenceRoleV02(str(lesson["evidence_role"]))

    evidence_refs = tuple(str(item) for item in lesson["evidence_refs"])
    provenance_refs = _unique(
        (
            str(provenance["action_digest"]),
            str(provenance["receipt_digest"]),
            *(str(item) for item in provenance["observer_evidence_digests"]),
            *(str(item) for item in provenance["source_event_ids"]),
        )
    )
    canonical_payload = _canonical_json(payload)

    return VerifiedEpisodeV02View(
        episode_id=str(payload["episode_id"]),
        causal_trace_id=str(provenance["causal_trace_id"]),
        created_at=str(payload["created_at"]),
        scope=str(lesson["scope"]),
        repeat_key=str(lesson["repeat_key"]),
        statement=str(lesson["statement"]),
        confidence=float(lesson["confidence"]),
        outcome_class=str(payload["outcome_class"]),
        evidence_role=role,
        expires_at=(
            str(lifecycle["expires_at"])
            if lifecycle.get("expires_at") is not None
            else None
        ),
        supersedes_episode_id=(
            str(lifecycle["supersedes_episode_id"])
            if lifecycle.get("supersedes_episode_id") is not None
            else None
        ),
        evidence_refs=evidence_refs,
        provenance_refs=provenance_refs,
        payload_digest="sha256:"
        + hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest(),
    )


def _validated_unique_views(
    payloads: Sequence[Mapping[str, Any]],
) -> tuple[VerifiedEpisodeV02View, ...]:
    views: list[VerifiedEpisodeV02View] = []
    seen_episode_ids: set[str] = set()
    seen_causal_trace_ids: set[str] = set()

    for payload in payloads:
        view = verified_episode_v02_view_from_mapping(payload)
        if view.episode_id in seen_episode_ids:
            raise IdentityLearningConsistencyError(
                f"duplicate v0.2 episode ID {view.episode_id!r}"
            )
        if view.causal_trace_id in seen_causal_trace_ids:
            raise IdentityLearningConsistencyError(
                f"duplicate v0.2 causal trace ID {view.causal_trace_id!r}"
            )
        seen_episode_ids.add(view.episode_id)
        seen_causal_trace_ids.add(view.causal_trace_id)
        views.append(view)

    return tuple(views)


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise IdentityLearningConsistencyError(
            f"v0.2 episode field {key!r} must be an object"
        )
    return value


def _instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise IdentityLearningConsistencyError(
            f"invalid RFC3339 timestamp {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise IdentityLearningConsistencyError(
            f"timestamp must include timezone {value!r}"
        )
    return parsed.astimezone(timezone.utc)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
