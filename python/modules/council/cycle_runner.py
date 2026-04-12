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
        constitution_row: dict[str, Any] | None = None
        policy_decision: dict[str, Any] = self._policy_decision(mode=mode, outcome=outcome)
        if isinstance(outcome.get("constitution"), dict):
            constitution_row = self.self_builder.store.store_constitution_evaluation(
                {
                    "cycle_id": cycle_id,
                    "mode": mode,
                    "snapshot_id": relational_self.snapshot_id,
                    "coherence_score": float(relational_self.self_coherence_score or 0.0),
                    "constitution": dict(outcome.get("constitution") or {}),
                    "blocked": bool(outcome.get("blocked", False)),
                    "policy_decision": policy_decision,
                }
            )
        if (
            execute_actions
            and str(mode) == "self-evolution-proposal"
            and bool(policy_decision.get("allow_auto_apply", False))
        ):
            for action in list(outcome.get("actions") or []):
                applied_actions.append(self._apply_action(action, relational_self=relational_self))
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
            "constitution_record": constitution_row,
            "policy_decision": policy_decision,
        }

    @staticmethod
    def _policy_decision(*, mode: str, outcome: dict[str, Any]) -> dict[str, Any]:
        if str(mode) != "self-evolution-proposal":
            return {
                "allow_auto_apply": False,
                "requires_review": False,
                "reason": "mode_not_evolution",
            }
        if bool(outcome.get("blocked", False)):
            return {
                "allow_auto_apply": False,
                "requires_review": True,
                "reason": "blocked_by_preservation",
            }
        constitution = outcome.get("constitution")
        if isinstance(constitution, dict):
            findings = list(constitution.get("findings") or [])
            escalate_failed = any(
                isinstance(item, dict)
                and str(item.get("severity") or "") == "escalate"
                and not bool(item.get("passed", True))
                for item in findings
            )
            if escalate_failed:
                return {
                    "allow_auto_apply": False,
                    "requires_review": True,
                    "reason": "constitution_escalate_violation",
                }
        return {
            "allow_auto_apply": True,
            "requires_review": False,
            "reason": "safe_for_auto_apply",
        }

    def _apply_action(self, action: dict[str, Any], *, relational_self: RelationalSelf) -> dict[str, Any]:
        action_name = str(action.get("action") or "")
        params = dict(action.get("params") or {})
        store = self.self_builder.store
        if action_name == "increase_reinforcing_edge_strength":
            max_delta = max(0.0, float(params.get("max_delta", 0.05) or 0.05))
            core_pairs = {
                (
                    str(edge.get("source_unit_id") or ""),
                    str(edge.get("target_unit_id") or ""),
                )
                for edge in list(relational_self.core_edges or [])
                if str(edge.get("relation_type") or "") == "reinforces"
            }
            updates = 0
            for unit in store.list_resonance_units():
                changed = False
                for rel in list(unit.relations or []):
                    if not isinstance(rel, dict):
                        continue
                    if str(rel.get("relation_type") or "") != "reinforces":
                        continue
                    pair = (unit.unit_id, str(rel.get("target_unit_id") or ""))
                    if core_pairs and pair not in core_pairs:
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
            base_window = max(25, len(relational_self.core_nodes or []))
            self.self_builder.update(
                source="council_action_expand_window",
                recent_window=base_window + recent_window_increment,
            )
            return {"action": action_name, "applied": True, "window_increment": recent_window_increment}

        return {"action": action_name, "applied": False, "reason": "unknown_action"}
