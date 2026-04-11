from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.cognition.relational_self import RelationalSelfBuilder
from modules.council.council_engine import RelationalCouncilEngine
from modules.graph.models import RelationalSelf


@dataclass
class CouncilCycleRunner:
    self_builder: RelationalSelfBuilder
    engine: RelationalCouncilEngine

    def run(
        self,
        *,
        cycle_id: str | None = None,
        mode: str = "self-consistency-check",
        omni_insight: dict[str, Any] | None = None,
        execute_actions: bool = False,
    ) -> dict[str, Any]:
        relational_self: RelationalSelf = self.self_builder.update(
            cycle_id=cycle_id,
            source="council_cycle",
            omni_insight=omni_insight,
        )
        outcome = self.engine.run_mode(mode=mode, relational_self=relational_self)
        applied_actions: list[dict[str, Any]] = []
        if execute_actions and str(mode) == "self-evolution-proposal":
            for action in list(outcome.get("actions") or []):
                applied_actions.append(self._apply_action(action))
            relational_self = self.self_builder.update(
                cycle_id=cycle_id,
                source="council_action_apply",
                omni_insight=omni_insight,
            )
        return {
            "cycle_id": cycle_id,
            "mode": mode,
            "relational_self": relational_self.to_dict(),
            "council_outcome": outcome,
            "relational_breach": self.engine.detect_breach(relational_self).__dict__,
            "applied_actions": applied_actions,
        }

    def _apply_action(self, action: dict[str, Any]) -> dict[str, Any]:
        action_name = str(action.get("action") or "")
        params = dict(action.get("params") or {})
        store = self.self_builder.store
        if action_name == "increase_reinforcing_edge_strength":
            max_delta = max(0.0, float(params.get("max_delta", 0.05) or 0.05))
            updates = 0
            for unit in store.list_resonance_units():
                changed = False
                for rel in list(unit.relations or []):
                    if not isinstance(rel, dict):
                        continue
                    if str(rel.get("relation_type") or "") != "reinforces":
                        continue
                    old_strength = float(rel.get("strength", 0.5) or 0.5)
                    rel["strength"] = round(min(1.0, old_strength + max_delta), 4)
                    changed = True
                    updates += 1
                if changed:
                    store.store_resonance_unit(unit)
            return {"action": action_name, "applied": True, "updated_edges": updates}

        if action_name == "expand_core_nodes_window":
            recent_window_increment = max(1, int(params.get("recent_window_increment", 5) or 5))
            self.self_builder.update(
                source="council_action_expand_window",
                recent_window=25 + recent_window_increment,
            )
            return {"action": action_name, "applied": True, "window_increment": recent_window_increment}

        return {"action": action_name, "applied": False, "reason": "unknown_action"}
