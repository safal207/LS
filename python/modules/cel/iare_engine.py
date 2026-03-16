from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from threading import RLock
import json


class IAREError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ContributorImpact:
    agent_id: str
    raw_impact: float
    resonance_factor: float = 1.0


@dataclass(frozen=True)
class CreationEvent:
    event_id: str
    project_id: str
    event_type: str
    ts: int
    policy_version: str
    contributors: tuple[ContributorImpact, ...]
    parents: tuple[str, ...] = ()
    base_weight: float = 1.0


@dataclass(frozen=True)
class PayoutLine:
    agent_id: str
    score: Decimal
    share: Decimal
    payout: Decimal


@dataclass(frozen=True)
class PayoutSnapshot:
    project_id: str
    policy_version: str
    input_snapshot_hash: str
    output_payout_hash: str
    lines: tuple[PayoutLine, ...]


@dataclass
class _ProjectState:
    events: dict[str, CreationEvent] = field(default_factory=dict)
    event_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    actor_totals: dict[str, float] = field(default_factory=dict)


@dataclass
class _CRDTValue:
    count_by_replica: dict[str, int] = field(default_factory=dict)
    pos_sum_by_replica: dict[str, float] = field(default_factory=dict)
    neg_sum_by_replica: dict[str, float] = field(default_factory=dict)

    def add(self, replica_id: str, score: float) -> None:
        self.count_by_replica[replica_id] = self.count_by_replica.get(replica_id, 0) + 1
        if score >= 0:
            self.pos_sum_by_replica[replica_id] = self.pos_sum_by_replica.get(replica_id, 0.0) + score
        else:
            self.neg_sum_by_replica[replica_id] = self.neg_sum_by_replica.get(replica_id, 0.0) + abs(score)

    def merge(self, other: _CRDTValue) -> None:
        self.count_by_replica = _merge_max(self.count_by_replica, other.count_by_replica)
        self.pos_sum_by_replica = _merge_max(self.pos_sum_by_replica, other.pos_sum_by_replica)
        self.neg_sum_by_replica = _merge_max(self.neg_sum_by_replica, other.neg_sum_by_replica)

    @property
    def count(self) -> int:
        return sum(self.count_by_replica.values())

    @property
    def sum_score(self) -> float:
        return sum(self.pos_sum_by_replica.values()) - sum(self.neg_sum_by_replica.values())


def _merge_max(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    keys = set(a) | set(b)
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in keys}


class CRDTReputationStore:
    """Merge-safe reputation store with PN-counter semantics for score."""

    def __init__(self) -> None:
        self._state: dict[str, _CRDTValue] = {}

    def add_score(self, actor_id: str, score: float, replica_id: str) -> None:
        current = self._state.setdefault(actor_id, _CRDTValue())
        current.add(replica_id=replica_id, score=score)

    def merge(self, other: CRDTReputationStore) -> None:
        for actor_id, value in other._state.items():
            mine = self._state.setdefault(actor_id, _CRDTValue())
            mine.merge(value)

    def get_smoothed_score(self, actor_id: str, prior: float = 0.5, alpha: float = 5.0) -> float:
        current = self._state.get(actor_id)
        if current is None:
            return prior
        return (alpha * prior + current.sum_score) / (alpha + current.count)


class IncrementalAttributionEngine:
    """Deterministic incremental attribution based on lineage decay.

    event_vector = self_vector + lineage_decay * Σ(parent_vector)
    """

    def __init__(self, lineage_decay: float = 0.75, max_depth: int = 6) -> None:
        if not 0 < lineage_decay <= 1:
            raise IAREError("INVALID_DECAY", "lineage_decay must be in (0,1]")
        if max_depth < 1:
            raise IAREError("INVALID_DEPTH", "max_depth must be >= 1")
        self._lineage_decay = lineage_decay
        self._max_depth = max_depth
        self._lock = RLock()
        self._projects: dict[str, _ProjectState] = {}

    def add_event(self, event: CreationEvent) -> bool:
        self._validate_event(event)
        with self._lock:
            state = self._projects.setdefault(event.project_id, _ProjectState())
            if event.event_id in state.events:
                return False

            for parent_id in event.parents:
                if parent_id not in state.events:
                    raise IAREError("MISSING_PARENT", f"unknown parent event: {parent_id}")

            own = self._own_vector(event)
            aggregate = dict(own)
            frontier: list[tuple[str, int]] = sorted((pid, 1) for pid in event.parents)
            while frontier:
                current_id, depth = frontier.pop(0)
                if depth > self._max_depth:
                    continue
                decay = self._lineage_decay**depth
                for actor_id, score in state.event_scores[current_id].items():
                    aggregate[actor_id] = aggregate.get(actor_id, 0.0) + score * decay
                current_event = state.events[current_id]
                for parent_id in sorted(current_event.parents):
                    frontier.append((parent_id, depth + 1))

            state.events[event.event_id] = event
            state.event_scores[event.event_id] = aggregate
            for actor_id, score in aggregate.items():
                state.actor_totals[actor_id] = state.actor_totals.get(actor_id, 0.0) + score
            return True

    def project_actor_scores(self, project_id: str) -> dict[str, float]:
        with self._lock:
            state = self._projects.get(project_id)
            if not state:
                return {}
            return dict(state.actor_totals)

    def build_payout_snapshot(self, project_id: str, policy_version: str, total_value: Decimal) -> PayoutSnapshot:
        if total_value <= 0:
            raise IAREError("INVALID_TOTAL_VALUE", "total_value must be > 0")

        with self._lock:
            state = self._projects.get(project_id)
            if not state or not state.actor_totals:
                raise IAREError("NO_SCORES", "no attribution scores for project")

            positive = {k: Decimal(str(v)) for k, v in state.actor_totals.items() if v > 0}
            if not positive:
                raise IAREError("NO_POSITIVE_SCORES", "all actor scores are <= 0")

            total_score = sum(positive.values(), start=Decimal("0"))
            lines: list[PayoutLine] = []
            cumulative_share = Decimal("0")
            actor_items = sorted(positive.items(), key=lambda it: it[0])
            for idx, (actor_id, score) in enumerate(actor_items):
                share = (score / total_score).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                if idx == len(actor_items) - 1:
                    share = Decimal("1") - cumulative_share
                cumulative_share += share
                payout = (total_value * share).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                lines.append(PayoutLine(agent_id=actor_id, score=score, share=share, payout=payout))

            input_payload = {
                "project_id": project_id,
                "policy_version": policy_version,
                "lineage_decay": self._lineage_decay,
                "max_depth": self._max_depth,
                "events": [
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "ts": event.ts,
                        "parents": sorted(event.parents),
                        "contributors": [
                            {
                                "agent_id": c.agent_id,
                                "raw_impact": c.raw_impact,
                                "resonance_factor": c.resonance_factor,
                            }
                            for c in sorted(event.contributors, key=lambda c: c.agent_id)
                        ],
                    }
                    for event in sorted(state.events.values(), key=lambda e: e.event_id)
                ],
            }
            output_payload = {
                "lines": [
                    {
                        "agent_id": line.agent_id,
                        "score": str(line.score),
                        "share": str(line.share),
                        "payout": str(line.payout),
                    }
                    for line in lines
                ]
            }
            input_snapshot_hash = _deterministic_hash(input_payload)
            output_payout_hash = _deterministic_hash(output_payload)
            return PayoutSnapshot(
                project_id=project_id,
                policy_version=policy_version,
                input_snapshot_hash=input_snapshot_hash,
                output_payout_hash=output_payout_hash,
                lines=tuple(lines),
            )

    @staticmethod
    def _validate_event(event: CreationEvent) -> None:
        if not event.event_id:
            raise IAREError("INVALID_EVENT_ID", "event_id is required")
        if not event.project_id:
            raise IAREError("INVALID_PROJECT_ID", "project_id is required")
        if not event.policy_version:
            raise IAREError("INVALID_POLICY", "policy_version is required")
        if event.base_weight <= 0:
            raise IAREError("INVALID_WEIGHT", "base_weight must be > 0")
        if not event.contributors:
            raise IAREError("INVALID_CONTRIBUTORS", "contributors is required")
        for contributor in event.contributors:
            if contributor.raw_impact < 0:
                raise IAREError("INVALID_IMPACT", "raw_impact must be >= 0")
            if contributor.resonance_factor < 0:
                raise IAREError("INVALID_RESONANCE", "resonance_factor must be >= 0")

    @staticmethod
    def _own_vector(event: CreationEvent) -> dict[str, float]:
        own: dict[str, float] = {}
        for contributor in event.contributors:
            score = event.base_weight * contributor.raw_impact * contributor.resonance_factor
            own[contributor.agent_id] = own.get(contributor.agent_id, 0.0) + score
        return own


def _deterministic_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
