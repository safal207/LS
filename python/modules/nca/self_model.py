from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SelfModel:
    """Tracks an internal identity model and projected self-state."""

    max_history: int = 100
    history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    identity_nodes: list[dict[str, Any]] = field(default_factory=list)
    identity_edges: list[dict[str, Any]] = field(default_factory=list)
    last_prediction: dict[str, Any] = field(default_factory=dict)
    cognitive_patterns: list[dict[str, Any]] = field(default_factory=list)
    bias_history: list[dict[str, Any]] = field(default_factory=list)
    cognitive_trace: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    identityintegritytrace: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    longtermstability_score: float = 1.0
    agency_markers: list[dict[str, Any]] = field(default_factory=list)
    intent_trace: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    intentstabilityscore: float = 1.0
    intentconflictmarkers: list[dict[str, Any]] = field(default_factory=list)
    autonomy_trace: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    autonomystabilityscore: float = 1.0
    selfdirectionmarkers: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Ensure deque length follows configured max_history.
        if self.history.maxlen != self.max_history:
            self.history = deque(self.history, maxlen=self.max_history)
        if self.cognitive_trace.maxlen != self.max_history:
            self.cognitive_trace = deque(self.cognitive_trace, maxlen=self.max_history)
        if self.identityintegritytrace.maxlen != self.max_history:
            self.identityintegritytrace = deque(self.identityintegritytrace, maxlen=self.max_history)
        if self.intent_trace.maxlen != self.max_history:
            self.intent_trace = deque(self.intent_trace, maxlen=self.max_history)
        if self.autonomy_trace.maxlen != self.max_history:
            self.autonomy_trace = deque(self.autonomy_trace, maxlen=self.max_history)

    def _extract_snapshot(self, agent_state: Any) -> dict[str, Any]:
        if hasattr(agent_state, "self_state"):
            self_state = getattr(agent_state, "self_state", {}) or {}
            t = getattr(agent_state, "t", len(self.history))
        else:
            self_state = agent_state if isinstance(agent_state, dict) else {}
            t = int(self_state.get("t", len(self.history))) if isinstance(self_state, dict) else len(self.history)

        personality = self_state.get("personality", {}) if isinstance(self_state, dict) else {}
        preferences = self_state.get("preferences", {}) if isinstance(self_state, dict) else {}

        snapshot = {
            "t": int(t),
            "preferences": {
                "progress": float(preferences.get("progress", 0.0)),
                "stability": float(preferences.get("stability", 0.0)),
            },
            "impulsiveness": float(personality.get("impulsiveness", 0.0)),
            "stability": float(personality.get("stability_preference", 0.0)),
            "risk": float(personality.get("risk_tolerance", 0.0)),
        }
        return snapshot

    def add_identity_node(self, state: dict[str, Any]) -> dict[str, Any]:
        node = {
            "id": len(self.identity_nodes),
            "t": int(state.get("t", len(self.identity_nodes))),
            "preferences": dict(state.get("preferences", {})),
            "impulsiveness": float(state.get("impulsiveness", 0.0)),
            "stability": float(state.get("stability", 0.0)),
            "risk": float(state.get("risk", 0.0)),
        }
        self.identity_nodes.append(node)
        if len(self.identity_nodes) > self.max_history:
            self.identity_nodes = self.identity_nodes[-self.max_history :]
        return node

    def add_transition(self, prev: dict[str, Any], nxt: dict[str, Any]) -> dict[str, Any]:
        pref_prev = prev.get("preferences", {})
        pref_next = nxt.get("preferences", {})
        delta = (
            abs(float(pref_next.get("progress", 0.0)) - float(pref_prev.get("progress", 0.0)))
            + abs(float(pref_next.get("stability", 0.0)) - float(pref_prev.get("stability", 0.0)))
            + abs(float(nxt.get("impulsiveness", 0.0)) - float(prev.get("impulsiveness", 0.0)))
            + abs(float(nxt.get("stability", 0.0)) - float(prev.get("stability", 0.0)))
            + abs(float(nxt.get("risk", 0.0)) - float(prev.get("risk", 0.0)))
        )
        edge = {
            "from": int(prev.get("id", max(0, len(self.identity_nodes) - 2))),
            "to": int(nxt.get("id", max(0, len(self.identity_nodes) - 1))),
            "weight": float(delta),
        }
        self.identity_edges.append(edge)
        if len(self.identity_edges) > self.max_history:
            self.identity_edges = self.identity_edges[-self.max_history :]
        return edge

    def update_from_state(self, agent_state: Any) -> dict[str, Any]:
        snapshot = self._extract_snapshot(agent_state)
        self.history.append(snapshot)
        node = self.add_identity_node(snapshot)

        if len(self.identity_nodes) >= 2:
            self.add_transition(self.identity_nodes[-2], self.identity_nodes[-1])

        self.last_prediction = self.predict_future_state(horizon=3)
        return node

    def drift_intensity(self) -> float:
        if not self.identity_edges:
            return 0.0
        avg = sum(float(edge.get("weight", 0.0)) for edge in self.identity_edges[-10:]) / min(10, len(self.identity_edges))
        return max(0.0, avg)

    def identity_drift_score(self) -> float:
        if len(self.history) < 2:
            return 0.0
        return self.drift_intensity()

    def predict_future_state(self, horizon: int = 3) -> dict[str, Any]:
        if not self.history:
            return {
                "horizon": horizon,
                "predicted": {
                    "preferences": {"progress": 0.0, "stability": 0.0},
                    "impulsiveness": 0.0,
                    "stability": 0.0,
                    "risk": 0.0,
                },
                "predictedselfconsistency": 1.0,
            }

        latest = dict(self.history[-1])
        prev = dict(self.history[-2]) if len(self.history) > 1 else latest

        def trend(key: str, is_pref: bool = False) -> float:
            if is_pref:
                return float(latest["preferences"].get(key, 0.0)) - float(prev["preferences"].get(key, 0.0))
            return float(latest.get(key, 0.0)) - float(prev.get(key, 0.0))

        predicted = {
            "preferences": {
                "progress": float(latest["preferences"].get("progress", 0.0)) + trend("progress", True) * horizon,
                "stability": float(latest["preferences"].get("stability", 0.0)) + trend("stability", True) * horizon,
            },
            "impulsiveness": float(latest.get("impulsiveness", 0.0)) + trend("impulsiveness") * horizon,
            "stability": float(latest.get("stability", 0.0)) + trend("stability") * horizon,
            "risk": float(latest.get("risk", 0.0)) + trend("risk") * horizon,
        }

        predicted_drift = (
            abs(trend("progress", True))
            + abs(trend("stability", True))
            + abs(trend("impulsiveness"))
            + abs(trend("stability"))
            + abs(trend("risk"))
        )
        predicted_consistency = max(0.0, min(1.0, 1.0 - min(1.0, predicted_drift)))

        result = {
            "horizon": horizon,
            "predicted": predicted,
            "predictedselfconsistency": predicted_consistency,
        }
        return result

    def meta_drift_score(self) -> float:
        if not self.cognitive_trace:
            return 0.0
        recent = list(self.cognitive_trace)[-8:]
        avg = sum(float(item.get("meta_drift", 0.0)) for item in recent) / len(recent)
        return max(0.0, min(1.0, avg))

    def update_cognitive_trace(self, state: Any, decision: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        self_state = getattr(state, "self_state", {}) if hasattr(state, "self_state") else {}
        personality = self_state.get("personality", {}) if isinstance(self_state, dict) else {}
        impulsiveness = float(personality.get("impulsiveness", 0.0))

        recent = list(self.cognitive_trace)[-1] if self.cognitive_trace else {}
        prev_impulsiveness = float(recent.get("impulsiveness", impulsiveness))
        impulsiveness_spikes = max(0.0, impulsiveness - prev_impulsiveness)
        over_correction = float(max(0.0, analysis.get("meta_drift", 0.0) - analysis.get("selfmodeldrift", 0.0)))
        oscillation = float(abs(analysis.get("self_consistency", 1.0) - analysis.get("predictedselfconsistency", 1.0)))
        repeated_drift = float(analysis.get("selfmodeldrift", 0.0))
        meta_drift = float(analysis.get("meta_drift", 0.0))

        entry = {
            "t": int(getattr(state, "t", len(self.cognitive_trace))),
            "decision": dict(decision or {}),
            "impulsiveness": impulsiveness,
            "impulsiveness_spikes": impulsiveness_spikes,
            "over_correction": over_correction,
            "oscillation": oscillation,
            "repeated_drift": repeated_drift,
            "meta_drift": meta_drift,
        }
        self.cognitive_trace.append(entry)

        pattern_scores = {
            "impulsiveness_spike": impulsiveness_spikes,
            "over_correction": over_correction,
            "oscillation": oscillation,
            "repeated_drift": repeated_drift,
            "meta_drift": meta_drift,
        }
        dominant_pattern = max(pattern_scores, key=pattern_scores.get)
        self.cognitive_patterns.append(
            {
                "t": entry["t"],
                "pattern": dominant_pattern,
                "score": float(pattern_scores[dominant_pattern]),
            }
        )
        if len(self.cognitive_patterns) > self.max_history:
            self.cognitive_patterns = self.cognitive_patterns[-self.max_history :]

        bias_labels = [name for name, value in pattern_scores.items() if value > 0.15]
        if bias_labels:
            self.bias_history.append({"t": entry["t"], "biases": bias_labels})
            if len(self.bias_history) > self.max_history:
                self.bias_history = self.bias_history[-self.max_history :]

        return entry

    def update_identity_metrics(self, identity_core: Any) -> dict[str, Any]:
        integrity = float(getattr(identity_core, "identity_integrity", 1.0))
        agency_level = float(getattr(identity_core, "agency_level", 0.0))
        drift_resistance = float(getattr(identity_core, "drift_resistance", 1.0))

        t = len(self.identityintegritytrace)
        entry = {
            "t": t,
            "identity_integrity": integrity,
            "agency_level": agency_level,
            "drift_resistance": drift_resistance,
        }
        self.identityintegritytrace.append(entry)

        recent = list(self.identityintegritytrace)[-8:]
        if recent:
            self.longtermstability_score = max(
                0.0,
                min(1.0, sum(float(item.get("identity_integrity", 1.0)) for item in recent) / len(recent)),
            )

        marker = {
            "t": t,
            "agency_signal": "high" if agency_level > 0.65 else "moderate" if agency_level > 0.35 else "low",
            "initiative_ready": agency_level > 0.5 and integrity > 0.55,
        }
        self.agency_markers.append(marker)
        if len(self.agency_markers) > self.max_history:
            self.agency_markers = self.agency_markers[-self.max_history :]
        return entry


    def update_intent_metrics(self, intent_engine: Any) -> dict[str, Any]:
        active = list(getattr(intent_engine, "active_intents", []))
        conflicts = list(getattr(intent_engine, "intent_conflicts", []))
        strength = float(getattr(intent_engine, "intent_strength", 0.0))
        alignment = float(getattr(intent_engine, "intent_alignment", 1.0))

        entry = {
            "t": len(self.intent_trace),
            "intents": [dict(i) for i in active],
            "intent_strength": strength,
            "intent_alignment": alignment,
            "conflict_count": len(conflicts),
        }
        self.intent_trace.append(entry)

        self.intentconflictmarkers.append(
            {
                "t": entry["t"],
                "conflicts": [dict(c) for c in conflicts],
                "conflict_score": min(1.0, len(conflicts) / 3.0),
            }
        )
        if len(self.intentconflictmarkers) > self.max_history:
            self.intentconflictmarkers = self.intentconflictmarkers[-self.max_history :]

        recent = list(self.intent_trace)[-8:]
        if recent:
            self.intentstabilityscore = max(
                0.0,
                min(
                    1.0,
                    sum(
                        max(0.0, min(1.0, float(item.get("intent_alignment", 0.0)) - (0.15 * float(item.get("conflict_count", 0.0)))))
                        for item in recent
                    )
                    / len(recent),
                ),
            )

        return entry

    def update_autonomy_metrics(self, autonomy_engine: Any) -> dict[str, Any]:
        level = float(getattr(autonomy_engine, "autonomy_level", 0.0))
        selected = getattr(autonomy_engine, "select_strategy", lambda: None)() or {}
        conflicts = list(getattr(autonomy_engine, "autonomy_conflicts", []))
        goals = list(getattr(autonomy_engine, "selfdirectedgoals", []))

        entry = {
            "t": len(self.autonomy_trace),
            "autonomy_level": level,
            "selected_strategy": dict(selected),
            "conflict_count": len(conflicts),
            "selfdirectedgoals": [dict(g) for g in goals],
        }
        self.autonomy_trace.append(entry)

        self.selfdirectionmarkers.append(
            {
                "t": entry["t"],
                "mode": str(selected.get("mode", "balanced")),
                "autonomy_signal": "high" if level > 0.65 else "moderate" if level > 0.4 else "low",
                "conflict_score": min(1.0, len(conflicts) / 3.0),
            }
        )
        if len(self.selfdirectionmarkers) > self.max_history:
            self.selfdirectionmarkers = self.selfdirectionmarkers[-self.max_history :]

        recent = list(self.autonomy_trace)[-8:]
        if recent:
            self.autonomystabilityscore = max(
                0.0,
                min(
                    1.0,
                    sum(
                        max(0.0, min(1.0, float(item.get("autonomy_level", 0.0)) - (0.12 * float(item.get("conflict_count", 0.0)))))
                        for item in recent
                    )
                    / len(recent),
                ),
            )

        return entry

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_history": self.max_history,
            "history": list(self.history),
            "identity_graph": {
                "nodes": list(self.identity_nodes),
                "edges": list(self.identity_edges),
            },
            "identity_drift_score": self.identity_drift_score(),
            "predicted_state": self.last_prediction or self.predict_future_state(horizon=3),
            "cognitive_patterns": list(self.cognitive_patterns),
            "bias_history": list(self.bias_history),
            "cognitive_trace": {
                "entries": list(self.cognitive_trace),
                "impulsiveness_spikes": max([float(e.get("impulsiveness_spikes", 0.0)) for e in self.cognitive_trace], default=0.0),
                "over_correction": max([float(e.get("over_correction", 0.0)) for e in self.cognitive_trace], default=0.0),
                "oscillation": max([float(e.get("oscillation", 0.0)) for e in self.cognitive_trace], default=0.0),
                "repeated_drift": max([float(e.get("repeated_drift", 0.0)) for e in self.cognitive_trace], default=0.0),
                "meta_drift": self.meta_drift_score(),
            },
            "meta_drift_score": self.meta_drift_score(),
            "identityintegritytrace": list(self.identityintegritytrace),
            "longterm_stability_score": self.longtermstability_score,
            "longtermstability_score": self.longtermstability_score,
            "agency_markers": list(self.agency_markers),
            "intent_trace": list(self.intent_trace),
            "intentstabilityscore": self.intentstabilityscore,
            "intentconflictmarkers": list(self.intentconflictmarkers),
            "autonomy_trace": list(self.autonomy_trace),
            "autonomystabilityscore": self.autonomystabilityscore,
            "selfdirectionmarkers": list(self.selfdirectionmarkers),
        }

    # Compatibility aliases requested by specification.
    def updatefromstate(self, agent_state: Any) -> dict[str, Any]:
        return self.update_from_state(agent_state)

    def predictfuturestate(self, horizon: int = 3) -> dict[str, Any]:
        return self.predict_future_state(horizon=horizon)

    def identitydriftscore(self) -> float:
        return self.identity_drift_score()

    def addidentitynode(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.add_identity_node(state)

    def metadriftscore(self) -> float:
        return self.meta_drift_score()

    def updatecognitivetrace(self, state: Any, decision: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        return self.update_cognitive_trace(state, decision, analysis)

    def updateidentitymetrics(self, identity_core: Any) -> dict[str, Any]:
        return self.update_identity_metrics(identity_core)


    def updateintentmetrics(self, intent_engine: Any) -> dict[str, Any]:
        return self.update_intent_metrics(intent_engine)

    def updateautonomymetrics(self, autonomy_engine: Any) -> dict[str, Any]:
        return self.update_autonomy_metrics(autonomy_engine)
