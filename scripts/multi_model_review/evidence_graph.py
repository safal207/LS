"""Living Evidence Graph primitives for exact-head review evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Iterable


def _parse_aware(value: str, field_name: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


class ArtifactKind(str, Enum):
    JSON_SCHEMA = "JSON_SCHEMA"
    VALIDATOR = "VALIDATOR"
    FIXTURE = "FIXTURE"
    TEST = "TEST"
    SPECIFICATION = "SPECIFICATION"
    WORKFLOW = "WORKFLOW"
    SOURCE = "SOURCE"


class Relation(str, Enum):
    IMPLEMENTS = "IMPLEMENTS"
    VALIDATES = "VALIDATES"
    TESTS = "TESTS"
    DOCUMENTS = "DOCUMENTS"
    INVOKES = "INVOKES"
    IMPORTS = "IMPORTS"
    OBSERVES = "OBSERVES"
    HARMONIZES = "HARMONIZES"


class EvidenceTier(str, Enum):
    T0_REPRODUCTION = "T0_REPRODUCTION"
    T1_STRUCTURAL = "T1_STRUCTURAL"
    T2_INDEPENDENT_MODELS = "T2_INDEPENDENT_MODELS"
    T3_MODEL_HYPOTHESIS = "T3_MODEL_HYPOTHESIS"


class SignalPhase(str, Enum):
    LATENT = "LATENT"
    UNFOLDED = "UNFOLDED"
    REPRODUCED = "REPRODUCED"
    CONFIRMED = "CONFIRMED"
    BLOCKING = "BLOCKING"
    FIXED = "FIXED"
    VERIFIED = "VERIFIED"
    DORMANT = "DORMANT"


_ALLOWED_PHASE_TRANSITIONS: dict[SignalPhase, set[SignalPhase]] = {
    SignalPhase.LATENT: {SignalPhase.UNFOLDED},
    SignalPhase.UNFOLDED: {SignalPhase.REPRODUCED},
    SignalPhase.REPRODUCED: {SignalPhase.CONFIRMED},
    SignalPhase.CONFIRMED: {SignalPhase.BLOCKING},
    SignalPhase.BLOCKING: {SignalPhase.FIXED},
    SignalPhase.FIXED: {SignalPhase.VERIFIED},
    SignalPhase.VERIFIED: {SignalPhase.DORMANT},
    SignalPhase.DORMANT: set(),
}


@dataclass(frozen=True)
class SpatialContext:
    repository: str
    base_sha: str
    head_sha: str
    branch: str | None = None
    workflow: str | None = None
    runtime: str | None = None

    def __post_init__(self) -> None:
        for name in ("base_sha", "head_sha"):
            value = getattr(self, name)
            if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{name} must be a lowercase 40-character SHA")


@dataclass(frozen=True)
class TemporalContext:
    observed_at: str
    valid_from: str | None = None
    valid_until: str | None = None
    superseded_at: str | None = None
    reconciled_at: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "observed_at",
            "valid_from",
            "valid_until",
            "superseded_at",
            "reconciled_at",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _parse_aware(value, field_name)


@dataclass(frozen=True)
class ArtifactNode:
    node_id: str
    path: str
    kind: ArtifactKind
    spatial: SpatialContext
    temporal: TemporalContext


@dataclass(frozen=True)
class ArtifactEdge:
    source: str
    relation: Relation
    target: str
    evidence: str


@dataclass(frozen=True)
class RelationHint:
    source_path: str
    relation: Relation
    target_path: str
    evidence: str

    def __post_init__(self) -> None:
        if not self.source_path or not self.target_path:
            raise ValueError("relation paths are required")
        if not self.evidence:
            raise ValueError("relation evidence is required")


@dataclass(frozen=True)
class Observation:
    observation_id: str
    method: str
    observer: str
    evidence: str
    repeatable: bool
    observed_at: str

    def __post_init__(self) -> None:
        _parse_aware(self.observed_at, "observed_at")


@dataclass(frozen=True)
class PhaseTransition:
    from_phase: SignalPhase
    to_phase: SignalPhase
    observation_id: str
    occurred_at: str

    def __post_init__(self) -> None:
        _parse_aware(self.occurred_at, "occurred_at")


@dataclass
class EvidenceSignal:
    signal_id: str
    title: str
    tier: EvidenceTier
    primary_artifact: str
    related_artifacts: list[str]
    violated_relation: Relation | None
    phase: SignalPhase = SignalPhase.LATENT
    observations: list[Observation] = field(default_factory=list)
    transitions: list[PhaseTransition] = field(default_factory=list)
    regression_rule: str | None = None

    def add_observation(self, observation: Observation) -> None:
        if any(item.observation_id == observation.observation_id for item in self.observations):
            raise ValueError(f"duplicate observation_id {observation.observation_id}")
        self.observations.append(observation)

    def advance(self, to_phase: SignalPhase, observation_id: str, occurred_at: str) -> None:
        if observation_id not in {item.observation_id for item in self.observations}:
            raise ValueError("phase transition requires an attributed observation")
        if to_phase not in _ALLOWED_PHASE_TRANSITIONS[self.phase]:
            raise ValueError(f"invalid phase transition {self.phase.value} -> {to_phase.value}")
        transition_time = _parse_aware(occurred_at, "occurred_at")
        observation = next(item for item in self.observations if item.observation_id == observation_id)
        if transition_time < _parse_aware(observation.observed_at, "observed_at"):
            raise ValueError("phase transition cannot precede its observation")
        if self.transitions and transition_time < _parse_aware(self.transitions[-1].occurred_at, "occurred_at"):
            raise ValueError("phase transitions must be time-monotonic")
        self.transitions.append(PhaseTransition(self.phase, to_phase, observation_id, occurred_at))
        self.phase = to_phase

    def preserve_regression_memory(self, rule_id: str) -> None:
        if self.phase != SignalPhase.DORMANT:
            raise ValueError("regression memory becomes dormant only after verification")
        if not rule_id:
            raise ValueError("rule_id is required")
        self.regression_rule = rule_id


@dataclass
class LivingEvidenceGraph:
    spatial: SpatialContext
    temporal: TemporalContext
    nodes: list[ArtifactNode]
    edges: list[ArtifactEdge]
    signals: list[EvidenceSignal] = field(default_factory=list)

    def add_signal(self, signal: EvidenceSignal) -> None:
        if any(item.signal_id == signal.signal_id for item in self.signals):
            raise ValueError(f"duplicate signal_id {signal.signal_id}")
        node_ids = {node.node_id for node in self.nodes}
        if signal.primary_artifact not in node_ids:
            raise ValueError("primary artifact is not in the graph")
        if any(node_id not in node_ids for node_id in signal.related_artifacts):
            raise ValueError("related artifact is not in the graph")
        self.signals.append(signal)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_artifact(path: str) -> ArtifactKind:
    lower = path.lower()
    name = PurePosixPath(lower).name
    if lower.startswith(".github/workflows/") and lower.endswith((".yml", ".yaml")):
        return ArtifactKind.WORKFLOW
    if name.endswith(".schema.json") or name in {"schema.json", "envelope.schema.json", "event.schema.json"}:
        return ArtifactKind.JSON_SCHEMA
    if lower.endswith(".json") and ("fixture" in lower or "fixtures/" in lower):
        return ArtifactKind.FIXTURE
    if name.startswith("test_") or "/tests/" in lower:
        return ArtifactKind.TEST
    if lower.endswith(".md") and ("spec/" in lower or "conformance" in lower or "docs/" in lower):
        return ArtifactKind.SPECIFICATION
    if lower.endswith(".py") and any(token in name for token in ("validate", "validator", "verify")):
        return ArtifactKind.VALIDATOR
    return ArtifactKind.SOURCE


def _node_id(path: str) -> str:
    return path.replace("/", "::")


def build_artifact_graph(
    paths: Iterable[str],
    *,
    repository: str,
    base_sha: str,
    head_sha: str,
    observed_at: str,
    branch: str | None = None,
    relation_hints: Iterable[RelationHint] = (),
) -> LivingEvidenceGraph:
    spatial = SpatialContext(repository, base_sha, head_sha, branch=branch)
    temporal = TemporalContext(observed_at=observed_at, valid_from=observed_at)
    unique_paths = sorted(set(paths))
    nodes = [
        ArtifactNode(_node_id(path), path, classify_artifact(path), spatial, temporal)
        for path in unique_paths
    ]
    known_paths = set(unique_paths)
    edges: list[ArtifactEdge] = []
    seen_edges: set[tuple[str, Relation, str]] = set()

    for hint in relation_hints:
        if hint.source_path not in known_paths:
            raise ValueError(f"relation source is not in graph: {hint.source_path}")
        if hint.target_path not in known_paths:
            raise ValueError(f"relation target is not in graph: {hint.target_path}")
        key = (hint.source_path, hint.relation, hint.target_path)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append(
            ArtifactEdge(
                source=_node_id(hint.source_path),
                relation=hint.relation,
                target=_node_id(hint.target_path),
                evidence=hint.evidence,
            )
        )

    return LivingEvidenceGraph(spatial=spatial, temporal=temporal, nodes=nodes, edges=edges)
