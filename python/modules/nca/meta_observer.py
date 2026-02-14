from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assembly import AgentState
from .orientation import OrientationCenter
from .signals import (
    COORDINATION_REQUIRED,
    MULTIAGENT_DRIFT,
    InternalSignal,
    SignalBus,
)


@dataclass
class MetaReport:
    self_consistency: float
    uncertainty: float
    drift: float
    micro_goals_status: dict[str, Any]
    causal_risk: bool = False
    causal_score: float = 0.0
    signals_emitted: list[dict[str, Any]] = field(default_factory=list)
    collective_score: float = 0.0
    collective_risk: float = 0.0
    collective_alignment: float = 1.0


@dataclass
class MetaObserver:
    """Monitors state for drift and emits orientation feedback."""

    drift_threshold: int = 2
    self_consistency_threshold: float = 0.45
    causal_alert_threshold: float = 0.4
    analysis_history: list[MetaReport] = field(default_factory=list)

    def analyze(self, state: AgentState, orientation: OrientationCenter) -> dict[str, Any]:
        drift_count = 0
        current_world = state.world_state
        current_pos = current_world.get("agent_position") if isinstance(current_world, dict) else None

        for event in state.history[-5:]:
            if event.get("action") == "idle":
                drift_count += 1
            if current_pos is not None and event.get("position_before") == current_pos:
                drift_count += 1

        self_consistency = orientation.compute_self_consistency(state)
        uncertainty = float(current_world.get("observation_uncertainty", 0.0)) if isinstance(current_world, dict) else 0.0

        causal_scores = [float(item.get("causal_score", 0.0)) for item in state.history[-6:] if "causal_score" in item]
        causal_score = sum(causal_scores) / len(causal_scores) if causal_scores else 0.0
        causal_risk = causal_score < self.causal_alert_threshold
        causal_drift = sum(1 for item in causal_scores if item < 0) >= 2

        collective_scores = [
            float(item.get("collective_score", item.get("analysis", {}).get("collective_score", 0.0)))
            for item in state.history[-8:]
        ]
        collective_score = sum(collective_scores) / len(collective_scores) if collective_scores else 0.0
        collective_drift = sum(1 for score in collective_scores if score < 0) >= 2
        collective_consistency = max(0.0, min(1.0, (self_consistency + (1.0 - min(1.0, abs(collective_score)) * 0.25)) / 2))
        collective_risk = max(0.0, min(1.0, (1.0 - collective_consistency) + (0.25 if collective_drift else 0.0)))

        return {
            "identity_drift_risk": drift_count >= self.drift_threshold,
            "drift_count": drift_count,
            "self_consistency": self_consistency,
            "uncertainty": uncertainty,
            "causal_score": causal_score,
            "causal_risk": causal_risk,
            "causal_drift": causal_drift,
            "collective_consistency": collective_consistency,
            "collective_drift": collective_drift,
            "collective_risk": collective_risk,
            "collective_score": collective_score,
            "collective_alignment": collective_consistency,
        }

    def stabilize(self, orientation: OrientationCenter, analysis: dict[str, Any]) -> None:
        if not analysis.get("identity_drift_risk"):
            return
        orientation.update_from_feedback(
            {
                "preference_updates": {"progress": 0.2, "stability": 0.1},
                "invariant_updates": {"avoid_idle_loops": True},
            }
        )

    def _emit_analysis_signals(
        self,
        analysis: dict[str, Any],
        signal_bus: SignalBus | None,
        state: AgentState,
    ) -> list[dict[str, Any]]:
        emitted: list[dict[str, Any]] = []
        if signal_bus is None:
            return emitted

        if analysis["self_consistency"] < self.self_consistency_threshold:
            sig = InternalSignal(
                signal_type="identitydriftdetected",
                t=state.t,
                payload={
                    "score": analysis["self_consistency"],
                    "threshold": self.self_consistency_threshold,
                },
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        if analysis["uncertainty"] >= 0.6:
            sig = InternalSignal(
                signal_type="world_uncertainty",
                t=state.t,
                payload={"uncertainty": analysis["uncertainty"]},
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        if analysis.get("identity_drift_risk"):
            sig = InternalSignal(
                signal_type="orientationfeedbackrequired",
                t=state.t,
                payload={"drift_count": analysis.get("drift_count", 0)},
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        if analysis.get("causal_risk"):
            sig = InternalSignal(
                signal_type="causalriskdetected",
                t=state.t,
                payload={
                    "causal_score": analysis.get("causal_score", 0.0),
                    "threshold": self.causal_alert_threshold,
                },
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        if analysis.get("causal_drift"):
            sig = InternalSignal(
                signal_type="causal_drift",
                t=state.t,
                payload={"causal_score": analysis.get("causal_score", 0.0)},
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        if analysis.get("collective_drift"):
            sig = InternalSignal(
                signal_type=MULTIAGENT_DRIFT,
                t=state.t,
                payload={"collective_score": analysis.get("collective_score", 0.0)},
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        if analysis.get("collective_risk", 0.0) >= 0.5:
            sig = InternalSignal(
                signal_type=COORDINATION_REQUIRED,
                t=state.t,
                payload={
                    "collective_risk": analysis.get("collective_risk", 0.0),
                    "collective_alignment": analysis.get("collective_alignment", 0.0),
                },
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        if analysis.get("causal_risk") and analysis.get("self_consistency", 1.0) < self.self_consistency_threshold:
            sig = InternalSignal(
                signal_type="causal_inconsistency",
                t=state.t,
                payload={
                    "causal_score": analysis.get("causal_score", 0.0),
                    "self_consistency": analysis.get("self_consistency", 0.0),
                },
            )
            signal_bus.emit(sig)
            emitted.append({"type": sig.signal_type, "payload": sig.payload})

        return emitted

    def generate_report(
        self,
        state: AgentState,
        orientation: OrientationCenter,
        signal_bus: SignalBus | None = None,
    ) -> MetaReport:
        analysis = self.analyze(state, orientation)
        emitted = self._emit_analysis_signals(analysis, signal_bus, state)
        report = MetaReport(
            self_consistency=analysis["self_consistency"],
            uncertainty=analysis["uncertainty"],
            drift=float(analysis.get("drift_count", 0)),
            causal_risk=bool(analysis.get("causal_risk", False)),
            causal_score=float(analysis.get("causal_score", 0.0)),
            micro_goals_status={
                "count": len(state.self_state.get("micro_goals", [])),
                "items": list(state.self_state.get("micro_goals", [])),
            },
            signals_emitted=emitted,
            collective_score=float(analysis.get("collective_score", 0.0)),
            collective_risk=float(analysis.get("collective_risk", 0.0)),
            collective_alignment=float(analysis.get("collective_alignment", 1.0)),
        )
        self.analysis_history.append(report)
        return report

    def observe_and_correct(
        self,
        state: AgentState,
        orientation: OrientationCenter,
        signal_bus: SignalBus | None = None,
    ) -> dict[str, Any]:
        analysis = self.analyze(state, orientation)
        self.stabilize(orientation, analysis)
        report = self.generate_report(state, orientation, signal_bus)
        return {
            **analysis,
            "report": report,
        }

    # Compatibility alias for requested naming.
    @property
    def causalalertthreshold(self) -> float:
        return self.causal_alert_threshold
