from __future__ import annotations

from .models import FutureScenario, NetworkSnapshot, TrajectoryRecord


class FuturePlanner:
    def build_scenarios(self, current: NetworkSnapshot, record: TrajectoryRecord) -> list[FutureScenario]:
        adequacy = current.adequacy_score
        drift = current.drift_score
        latency_cost = round(1.0 - current.latency_score, 4)

        return [
            FutureScenario(
                scenario_id="safe-stabilization",
                title="Safe Stabilization",
                assumptions=["reduce aggressive promotions", "prefer trusted routes", "increase care-cycle attention"],
                expected_benefits=["lower drift", "more predictable adequacy"],
                expected_risks=["slower exploration", "less novelty"],
                projected_adequacy=round(min(1.0, adequacy + 0.04), 4),
                projected_cost=round(max(0.0, latency_cost + 0.03), 4),
            ),
            FutureScenario(
                scenario_id="efficient-expansion",
                title="Efficient Expansion",
                assumptions=["use more derived modules", "keep strong coalitions as fallback"],
                expected_benefits=["lower runtime cost", "faster common answers"],
                expected_risks=["module drift if care cycles lag"],
                projected_adequacy=round(max(0.0, adequacy - 0.01 if drift > 0.3 else adequacy + 0.02), 4),
                projected_cost=round(max(0.0, latency_cost - 0.08), 4),
            ),
            FutureScenario(
                scenario_id="aggressive-exploration",
                title="Aggressive Exploration",
                assumptions=["raise exploration rate", "test new coalition variants"],
                expected_benefits=["discover stronger future routes"],
                expected_risks=["temporary coherence loss", "higher latency variance"],
                projected_adequacy=round(max(0.0, adequacy - 0.03), 4),
                projected_cost=round(min(1.0, latency_cost + 0.08), 4),
            ),
        ]
