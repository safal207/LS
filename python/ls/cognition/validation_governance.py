from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from ls.cognition.lifetra_validation_adapter import _safe_preview

if TYPE_CHECKING:
    from ls.cognition.collective_answer_validator import ValidationInput, ValidationResult


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _clamp(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalized_tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _token_shingles(text: str, *, size: int = 2) -> set[str]:
    tokens = _normalized_tokens(text)
    if not tokens:
        return set()
    if len(tokens) < size:
        return {" ".join(tokens)}
    return {" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _text_similarity(left: str, right: str) -> float:
    token_score = _jaccard_similarity(set(_normalized_tokens(left)), set(_normalized_tokens(right)))
    shingle_score = _jaccard_similarity(_token_shingles(left), _token_shingles(right))
    return max(token_score, shingle_score)


@dataclass(frozen=True)
class ValidationHistoryCandidate:
    agent_id: str
    accepted: bool
    base_score: float
    adjusted_score: float
    answer_preview: str
    support_ids: list[str] = field(default_factory=list)
    contradiction_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationHistoryRecord:
    round_id: str
    winner_agent_id: str | None
    governed_winner_agent_id: str | None
    consensus_status: str
    global_risk_flags: list[str]
    coalition_alert_agent_ids: list[str]
    paraphrase_clusters: list[list[str]]
    candidates: list[ValidationHistoryCandidate]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ValidationHistoryRecord:
        return cls(
            round_id=str(payload.get("round_id", "")),
            winner_agent_id=payload.get("winner_agent_id"),
            governed_winner_agent_id=payload.get("governed_winner_agent_id"),
            consensus_status=str(payload.get("consensus_status", "unknown")),
            global_risk_flags=list(payload.get("global_risk_flags", [])),
            coalition_alert_agent_ids=list(payload.get("coalition_alert_agent_ids", [])),
            paraphrase_clusters=[
                list(cluster) for cluster in payload.get("paraphrase_clusters", [])
            ],
            candidates=[
                ValidationHistoryCandidate(**candidate)
                for candidate in payload.get("candidates", [])
            ],
        )


class ValidationHistoryStore(Protocol):
    def load_records(self) -> list[ValidationHistoryRecord]: ...

    def append_record(self, record: ValidationHistoryRecord) -> None: ...


class InMemoryValidationHistoryStore:
    def __init__(self) -> None:
        self._records: list[ValidationHistoryRecord] = []

    def load_records(self) -> list[ValidationHistoryRecord]:
        return list(self._records)

    def append_record(self, record: ValidationHistoryRecord) -> None:
        self._records.append(record)


class JsonlValidationHistoryStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load_records(self) -> list[ValidationHistoryRecord]:
        if not self._path.exists():
            return []
        records: list[ValidationHistoryRecord] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(ValidationHistoryRecord.from_dict(json.loads(line)))
        return records

    def append_record(self, record: ValidationHistoryRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
            handle.write("\n")


@dataclass(frozen=True)
class ParaphraseCluster:
    cluster_id: str
    agent_ids: list[str]
    suspicious: bool
    average_similarity: float
    previews: list[str]


@dataclass(frozen=True)
class AgentReputationProfile:
    agent_id: str
    rounds_seen: int
    weighted_rounds_seen: float
    accepted_count: int
    winner_count: int
    conflict_count: int
    echo_count: int
    coalition_alert_count: int
    reputation_score: float
    trust_tier: str


@dataclass(frozen=True)
class GovernedCandidateScore:
    agent_id: str
    base_score: float
    adjusted_score: float
    total_adjustment: float
    reputation_adjustment: float
    paraphrase_adjustment: float
    coalition_adjustment: float
    risk_adjustment: float
    reasons: list[str]


@dataclass(frozen=True)
class CoalitionAlert:
    coalition_id: str
    agent_ids: list[str]
    alert_kind: str
    severity: str
    confidence: float
    evidence_count: int
    reason: str


@dataclass(frozen=True)
class DistributedConsensusSnapshot:
    quorum_size: int
    trusted_support_count: int
    trusted_support_agent_ids: list[str]
    trusted_contradiction_count: int
    trusted_contradiction_agent_ids: list[str]
    veto_present: bool
    quorum_reached: bool
    status: str
    governed_winner_agent_id: str | None


@dataclass(frozen=True)
class ValidationGovernanceReport:
    backend: str
    history_round_count: int
    paraphrase_clusters: list[ParaphraseCluster]
    agent_profiles: list[AgentReputationProfile]
    adjusted_candidates: list[GovernedCandidateScore]
    coalition_alerts: list[CoalitionAlert]
    distributed_consensus: DistributedConsensusSnapshot
    governed_winner_agent_id: str | None
    governance_flags: list[str]
    escalation_recommendations: list[str]
    review_required: bool


class ValidationGovernanceEngine:
    def __init__(
        self,
        *,
        history_store: ValidationHistoryStore | None = None,
        paraphrase_threshold: float = 0.58,
        coalition_repeat_threshold: int = 3,
        quorum_size: int = 2,
        trusted_reputation_threshold: float = 0.52,
        history_decay: float = 0.82,
    ) -> None:
        self._history_store = history_store or InMemoryValidationHistoryStore()
        self._paraphrase_threshold = paraphrase_threshold
        self._coalition_repeat_threshold = coalition_repeat_threshold
        self._quorum_size = quorum_size
        self._trusted_reputation_threshold = trusted_reputation_threshold
        self._history_decay = history_decay

    def build_governance_report(
        self,
        payload: ValidationInput,
        result: ValidationResult,
    ) -> ValidationGovernanceReport:
        history = self._history_store.load_records()
        profiles_by_agent = self._build_reputation_profiles(history)
        paraphrase_clusters = self._detect_paraphrase_clusters(payload)
        coalition_alerts = self._detect_coalition_alerts(
            payload=payload,
            result=result,
            history=history,
            paraphrase_clusters=paraphrase_clusters,
        )
        adjusted_candidates = self._build_adjusted_candidates(
            payload=payload,
            result=result,
            profiles_by_agent=profiles_by_agent,
            paraphrase_clusters=paraphrase_clusters,
            coalition_alerts=coalition_alerts,
        )
        governed_winner_agent_id = adjusted_candidates[0].agent_id if adjusted_candidates else None
        distributed_consensus = self._build_distributed_consensus(
            payload=payload,
            result=result,
            profiles_by_agent=profiles_by_agent,
            adjusted_candidates=adjusted_candidates,
            governed_winner_agent_id=governed_winner_agent_id,
        )
        governance_flags = self._build_governance_flags(
            result=result,
            paraphrase_clusters=paraphrase_clusters,
            coalition_alerts=coalition_alerts,
            distributed_consensus=distributed_consensus,
            profiles_by_agent=profiles_by_agent,
            governed_winner_agent_id=governed_winner_agent_id,
        )
        escalation_recommendations = self._build_escalation_recommendations(
            result=result,
            coalition_alerts=coalition_alerts,
            distributed_consensus=distributed_consensus,
            governed_winner_agent_id=governed_winner_agent_id,
        )
        review_required = bool(
            escalation_recommendations
            or "governed_winner_differs_from_base" in governance_flags
            or "trusted_veto_present" in governance_flags
        )

        report = ValidationGovernanceReport(
            backend="deterministic_governance_v1",
            history_round_count=len(history),
            paraphrase_clusters=paraphrase_clusters,
            agent_profiles=sorted(
                profiles_by_agent.values(),
                key=lambda profile: (-profile.reputation_score, profile.agent_id),
            ),
            adjusted_candidates=adjusted_candidates,
            coalition_alerts=coalition_alerts,
            distributed_consensus=distributed_consensus,
            governed_winner_agent_id=governed_winner_agent_id,
            governance_flags=governance_flags,
            escalation_recommendations=escalation_recommendations,
            review_required=review_required,
        )
        self._history_store.append_record(
            self._to_history_record(
                payload=payload,
                result=result,
                report=report,
            )
        )
        return report

    def _build_reputation_profiles(
        self,
        history: list[ValidationHistoryRecord],
    ) -> dict[str, AgentReputationProfile]:
        stats: dict[str, dict[str, float]] = {}
        for offset, record in enumerate(reversed(history)):
            weight = self._history_decay**offset
            paraphrase_agents = {
                agent_id
                for cluster in record.paraphrase_clusters
                if len(cluster) >= 2
                for agent_id in cluster
            }
            coalition_agents = set(record.coalition_alert_agent_ids)
            for candidate in record.candidates:
                bucket = stats.setdefault(
                    candidate.agent_id,
                    {
                        "rounds_seen": 0.0,
                        "weighted_rounds_seen": 0.0,
                        "accepted_count": 0.0,
                        "winner_count": 0.0,
                        "conflict_count": 0.0,
                        "echo_count": 0.0,
                        "coalition_alert_count": 0.0,
                    },
                )
                bucket["rounds_seen"] += 1.0
                bucket["weighted_rounds_seen"] += weight
                bucket["accepted_count"] += weight if candidate.accepted else 0.0
                bucket["winner_count"] += weight if record.winner_agent_id == candidate.agent_id else 0.0
                bucket["conflict_count"] += weight if "conflict_between_top_candidates" in record.global_risk_flags else 0.0
                bucket["echo_count"] += weight if candidate.agent_id in paraphrase_agents else 0.0
                bucket["coalition_alert_count"] += weight if candidate.agent_id in coalition_agents else 0.0

        profiles: dict[str, AgentReputationProfile] = {}
        for agent_id, bucket in stats.items():
            rounds_seen = int(bucket["rounds_seen"])
            weighted_rounds_seen = max(bucket["weighted_rounds_seen"], 1e-6)
            accepted_rate = bucket["accepted_count"] / weighted_rounds_seen
            winner_rate = bucket["winner_count"] / weighted_rounds_seen
            conflict_rate = bucket["conflict_count"] / weighted_rounds_seen
            echo_rate = bucket["echo_count"] / weighted_rounds_seen
            coalition_rate = bucket["coalition_alert_count"] / weighted_rounds_seen
            reputation_score = _clamp(
                0.5
                + (0.30 * accepted_rate)
                + (0.18 * winner_rate)
                - (0.18 * conflict_rate)
                - (0.15 * echo_rate)
                - (0.24 * coalition_rate)
            )
            trust_tier = self._trust_tier(reputation_score)
            profiles[agent_id] = AgentReputationProfile(
                agent_id=agent_id,
                rounds_seen=rounds_seen,
                weighted_rounds_seen=round(weighted_rounds_seen, 4),
                accepted_count=int(bucket["accepted_count"]),
                winner_count=int(bucket["winner_count"]),
                conflict_count=int(bucket["conflict_count"]),
                echo_count=int(bucket["echo_count"]),
                coalition_alert_count=int(bucket["coalition_alert_count"]),
                reputation_score=round(reputation_score, 4),
                trust_tier=trust_tier,
            )
        return profiles

    @staticmethod
    def _trust_tier(reputation_score: float) -> str:
        if reputation_score >= 0.75:
            return "trusted"
        if reputation_score >= 0.58:
            return "watch"
        if reputation_score >= 0.42:
            return "probing"
        return "untrusted"

    def _detect_paraphrase_clusters(
        self,
        payload: ValidationInput,
    ) -> list[ParaphraseCluster]:
        candidate_ids = [candidate.agent_id for candidate in payload.candidates]
        parents = {agent_id: agent_id for agent_id in candidate_ids}
        similarities: dict[tuple[str, str], float] = {}

        def find(agent_id: str) -> str:
            while parents[agent_id] != agent_id:
                parents[agent_id] = parents[parents[agent_id]]
                agent_id = parents[agent_id]
            return agent_id

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for index, left in enumerate(payload.candidates):
            for right in payload.candidates[index + 1 :]:
                similarity = _text_similarity(left.answer_text, right.answer_text)
                if similarity >= self._paraphrase_threshold:
                    union(left.agent_id, right.agent_id)
                    similarities[(left.agent_id, right.agent_id)] = similarity

        groups: dict[str, list[str]] = {}
        for agent_id in candidate_ids:
            groups.setdefault(find(agent_id), []).append(agent_id)

        payload_by_agent = {candidate.agent_id: candidate for candidate in payload.candidates}
        clusters: list[ParaphraseCluster] = []
        for agent_ids in groups.values():
            if len(agent_ids) < 2:
                continue
            pair_scores = []
            for index, left in enumerate(agent_ids):
                for right in agent_ids[index + 1 :]:
                    pair_scores.append(
                        similarities.get((left, right))
                        or similarities.get((right, left))
                        or _text_similarity(
                            payload_by_agent[left].answer_text,
                            payload_by_agent[right].answer_text,
                        )
                    )
            average_similarity = sum(pair_scores) / len(pair_scores)
            suspicious = average_similarity >= self._paraphrase_threshold
            cluster_seed = "|".join(sorted(agent_ids))
            clusters.append(
                ParaphraseCluster(
                    cluster_id=f"cluster:{abs(hash(cluster_seed))}",
                    agent_ids=sorted(agent_ids),
                    suspicious=suspicious,
                    average_similarity=round(average_similarity, 4),
                    previews=[
                        _safe_preview(payload_by_agent[agent_id].answer_text, 60)
                        for agent_id in sorted(agent_ids)
                    ],
                )
            )
        return sorted(clusters, key=lambda cluster: (-len(cluster.agent_ids), cluster.cluster_id))

    def _detect_coalition_alerts(
        self,
        *,
        payload: ValidationInput,
        result: ValidationResult,
        history: list[ValidationHistoryRecord],
        paraphrase_clusters: list[ParaphraseCluster],
    ) -> list[CoalitionAlert]:
        history_pair_counts: dict[tuple[str, str], int] = {}
        for record in history:
            for cluster in record.paraphrase_clusters:
                if len(cluster) < 2:
                    continue
                for index, left in enumerate(sorted(cluster)):
                    for right in sorted(cluster)[index + 1 :]:
                        history_pair_counts[(left, right)] = history_pair_counts.get((left, right), 0) + 1

        current_pairs: list[tuple[str, str]] = []
        for cluster in paraphrase_clusters:
            for index, left in enumerate(cluster.agent_ids):
                for right in cluster.agent_ids[index + 1 :]:
                    current_pairs.append((left, right))

        support_pairs = {
            tuple(sorted((candidate.agent_id, target_agent_id)))
            for candidate in payload.candidates
            for target_agent_id in candidate.supports
        }
        contradiction_edges = {
            (candidate.agent_id, target_agent_id)
            for candidate in payload.candidates
            for target_agent_id in candidate.contradicts
        }

        alerts: list[CoalitionAlert] = []
        for pair in sorted(set(current_pairs) | support_pairs):
            evidence_count = history_pair_counts.get(pair, 0) + (1 if pair in current_pairs else 0)
            if evidence_count < self._coalition_repeat_threshold:
                continue
            contradiction_to_outsiders = any(
                left in pair and right not in pair
                for left, right in contradiction_edges
            )
            confidence = _clamp(0.4 + (0.15 * evidence_count) + (0.15 if pair in support_pairs else 0.0))
            kind = "paraphrase_coalition"
            reason = f"Repeated paraphrase/support alignment detected for pair={pair!r}"
            if contradiction_to_outsiders:
                kind = "corruption_risk"
                reason = f"Repeated alignment plus outsider contradiction detected for pair={pair!r}"
                confidence = _clamp(confidence + 0.1)
            severity = "medium"
            if confidence >= 0.8 or kind == "corruption_risk":
                severity = "high"
            elif confidence < 0.6:
                severity = "low"
            alerts.append(
                CoalitionAlert(
                    coalition_id=f"coalition:{pair[0]}::{pair[1]}",
                    agent_ids=list(pair),
                    alert_kind=kind,
                    severity=severity,
                    confidence=round(confidence, 4),
                    evidence_count=evidence_count,
                    reason=reason,
                )
            )
        return alerts

    def _build_adjusted_candidates(
        self,
        *,
        payload: ValidationInput,
        result: ValidationResult,
        profiles_by_agent: dict[str, AgentReputationProfile],
        paraphrase_clusters: list[ParaphraseCluster],
        coalition_alerts: list[CoalitionAlert],
    ) -> list[GovernedCandidateScore]:
        suspicious_cluster_map = {
            agent_id: cluster
            for cluster in paraphrase_clusters
            if cluster.suspicious
            for agent_id in cluster.agent_ids
        }
        coalition_map = {
            agent_id: alert
            for alert in coalition_alerts
            for agent_id in alert.agent_ids
        }
        adjusted: list[GovernedCandidateScore] = []
        for candidate in result.ranked_candidates:
            profile = profiles_by_agent.get(candidate.agent_id)
            reputation_adjustment = 0.0
            reasons: list[str] = []
            if profile is not None:
                tier_bonus = {
                    "trusted": 0.02,
                    "watch": 0.0,
                    "probing": -0.01,
                    "untrusted": -0.03,
                }[profile.trust_tier]
                reputation_adjustment = round(((profile.reputation_score - 0.5) * 0.14) + tier_bonus, 4)
                if not math.isclose(reputation_adjustment, 0.0):
                    reasons.append(
                        f"reputation={profile.reputation_score:.3f} tier={profile.trust_tier} adjustment={reputation_adjustment:+.3f}"
                    )

            paraphrase_adjustment = 0.0
            cluster = suspicious_cluster_map.get(candidate.agent_id)
            if cluster is not None:
                paraphrase_adjustment = round(-0.04 * max(len(cluster.agent_ids) - 1, 1), 4)
                reasons.append(
                    f"paraphrase_cluster={cluster.cluster_id} members={len(cluster.agent_ids)}"
                )

            coalition_adjustment = 0.0
            alert = coalition_map.get(candidate.agent_id)
            if alert is not None:
                severity_multiplier = {"low": 0.8, "medium": 1.0, "high": 1.25}[alert.severity]
                coalition_adjustment = round(-0.08 * alert.confidence * severity_multiplier, 4)
                reasons.append(
                    f"coalition_alert={alert.alert_kind} severity={alert.severity} confidence={alert.confidence:.3f}"
                )

            risk_adjustment = 0.0
            if "conflict_between_top_candidates" in result.global_risk_flags and candidate.accepted:
                risk_adjustment -= 0.03
                reasons.append("conflict_between_top_candidates")
            if "possible_echo_chamber" in result.global_risk_flags and cluster is not None:
                risk_adjustment -= 0.03
                reasons.append("possible_echo_chamber")

            total_adjustment = round(
                reputation_adjustment
                + paraphrase_adjustment
                + coalition_adjustment
                + risk_adjustment,
                4,
            )
            adjusted_score = round(_clamp(candidate.score + total_adjustment), 4)
            adjusted.append(
                GovernedCandidateScore(
                    agent_id=candidate.agent_id,
                    base_score=round(candidate.score, 4),
                    adjusted_score=adjusted_score,
                    total_adjustment=total_adjustment,
                    reputation_adjustment=reputation_adjustment,
                    paraphrase_adjustment=paraphrase_adjustment,
                    coalition_adjustment=round(coalition_adjustment, 4),
                    risk_adjustment=round(risk_adjustment, 4),
                    reasons=reasons,
                )
            )
        return sorted(adjusted, key=lambda item: (-item.adjusted_score, item.agent_id))

    def _build_distributed_consensus(
        self,
        *,
        payload: ValidationInput,
        result: ValidationResult,
        profiles_by_agent: dict[str, AgentReputationProfile],
        adjusted_candidates: list[GovernedCandidateScore],
        governed_winner_agent_id: str | None,
    ) -> DistributedConsensusSnapshot:
        if governed_winner_agent_id is None:
            return DistributedConsensusSnapshot(
                quorum_size=self._quorum_size,
                trusted_support_count=0,
                trusted_support_agent_ids=[],
                trusted_contradiction_count=0,
                trusted_contradiction_agent_ids=[],
                veto_present=False,
                quorum_reached=False,
                status="rejected",
                governed_winner_agent_id=None,
            )

        adjusted_by_agent = {candidate.agent_id: candidate for candidate in adjusted_candidates}
        trusted_support_agent_ids: list[str] = []
        trusted_contradiction_agent_ids: list[str] = []
        veto_targets = {
            target
            for target in (governed_winner_agent_id, result.winner_agent_id)
            if target is not None
        }
        for candidate in payload.candidates:
            if candidate.agent_id not in adjusted_by_agent:
                continue
            profile = profiles_by_agent.get(candidate.agent_id)
            reputation_score = profile.reputation_score if profile is not None else 0.5
            adjusted_score = adjusted_by_agent[candidate.agent_id].adjusted_score
            supports_winner = governed_winner_agent_id in candidate.supports
            contradicts_winner = any(
                veto_target in candidate.contradicts for veto_target in veto_targets
            )
            is_winner = candidate.agent_id == governed_winner_agent_id
            if adjusted_score < 0.45 or reputation_score < self._trusted_reputation_threshold:
                continue
            if is_winner or supports_winner:
                trusted_support_agent_ids.append(candidate.agent_id)
            if contradicts_winner:
                trusted_contradiction_agent_ids.append(candidate.agent_id)

        veto_present = bool(trusted_contradiction_agent_ids)
        conflict_present = veto_present or any(
            candidate.agent_id == governed_winner_agent_id and candidate.contradicts
            for candidate in payload.candidates
        )
        quorum_reached = len(trusted_support_agent_ids) >= self._quorum_size and not veto_present
        status = "quorum" if quorum_reached else "weak_quorum"
        if veto_present:
            status = "vetoed"
        elif conflict_present:
            status = "conflicted_quorum"
        return DistributedConsensusSnapshot(
            quorum_size=self._quorum_size,
            trusted_support_count=len(trusted_support_agent_ids),
            trusted_support_agent_ids=sorted(trusted_support_agent_ids),
            trusted_contradiction_count=len(trusted_contradiction_agent_ids),
            trusted_contradiction_agent_ids=sorted(trusted_contradiction_agent_ids),
            veto_present=veto_present,
            quorum_reached=quorum_reached,
            status=status,
            governed_winner_agent_id=governed_winner_agent_id,
        )

    def _build_governance_flags(
        self,
        *,
        result: ValidationResult,
        paraphrase_clusters: list[ParaphraseCluster],
        coalition_alerts: list[CoalitionAlert],
        distributed_consensus: DistributedConsensusSnapshot,
        profiles_by_agent: dict[str, AgentReputationProfile],
        governed_winner_agent_id: str | None,
    ) -> list[str]:
        flags = list(result.global_risk_flags)
        if any(cluster.suspicious for cluster in paraphrase_clusters):
            flags.append("semantic_paraphrase_cluster")
        if coalition_alerts:
            flags.append("coalition_risk_detected")
        if not distributed_consensus.quorum_reached:
            flags.append("distributed_quorum_missing")
        if distributed_consensus.veto_present:
            flags.append("trusted_veto_present")
        if governed_winner_agent_id is not None:
            profile = profiles_by_agent.get(governed_winner_agent_id)
            if profile is not None and profile.reputation_score < self._trusted_reputation_threshold:
                flags.append("low_trust_governed_winner")
        if governed_winner_agent_id != result.winner_agent_id:
            flags.append("governed_winner_differs_from_base")
        return sorted(dict.fromkeys(flags))

    def _build_escalation_recommendations(
        self,
        *,
        result: ValidationResult,
        coalition_alerts: list[CoalitionAlert],
        distributed_consensus: DistributedConsensusSnapshot,
        governed_winner_agent_id: str | None,
    ) -> list[str]:
        recommendations: list[str] = []
        if governed_winner_agent_id != result.winner_agent_id:
            recommendations.append(
                "Base validator winner and governed winner diverged; require operator review before finalizing."
            )
        if any(alert.alert_kind == "corruption_risk" or alert.severity == "high" for alert in coalition_alerts):
            recommendations.append(
                "High-risk coalition pattern detected; quarantine coalition output for human review."
            )
        if distributed_consensus.veto_present:
            recommendations.append(
                "Trusted contradiction veto is present; do not treat this round as settled consensus."
            )
        if not distributed_consensus.quorum_reached:
            recommendations.append(
                "Trusted quorum is missing; keep the outcome advisory until more independent support arrives."
            )
        return recommendations

    def _to_history_record(
        self,
        *,
        payload: ValidationInput,
        result: ValidationResult,
        report: ValidationGovernanceReport,
    ) -> ValidationHistoryRecord:
        adjusted_by_agent = {
            candidate.agent_id: candidate.adjusted_score for candidate in report.adjusted_candidates
        }
        candidates = [
            ValidationHistoryCandidate(
                agent_id=validated.agent_id,
                accepted=validated.accepted,
                base_score=round(validated.score, 4),
                adjusted_score=round(adjusted_by_agent.get(validated.agent_id, validated.score), 4),
                answer_preview=_safe_preview(payload_candidate.answer_text, 60),
                support_ids=list(payload_candidate.supports),
                contradiction_ids=list(payload_candidate.contradicts),
            )
            for validated in result.ranked_candidates
            for payload_candidate in payload.candidates
            if payload_candidate.agent_id == validated.agent_id
        ]
        coalition_alert_agent_ids = sorted(
            {
                agent_id
                for alert in report.coalition_alerts
                for agent_id in alert.agent_ids
            }
        )
        round_seed = "|".join(
            [
                result.winner_agent_id or "none",
                report.governed_winner_agent_id or "none",
                result.consensus_status,
                ",".join(candidate.agent_id for candidate in result.ranked_candidates),
            ]
        )
        return ValidationHistoryRecord(
            round_id=f"round:{abs(hash(round_seed))}",
            winner_agent_id=result.winner_agent_id,
            governed_winner_agent_id=report.governed_winner_agent_id,
            consensus_status=result.consensus_status,
            global_risk_flags=list(report.governance_flags),
            coalition_alert_agent_ids=coalition_alert_agent_ids,
            paraphrase_clusters=[list(cluster.agent_ids) for cluster in report.paraphrase_clusters],
            candidates=candidates,
        )
