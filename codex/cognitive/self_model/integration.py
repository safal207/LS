from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from codex.lpi import PresenceMonitor
from codex.selector import AdaptiveModelSelector, SelectionResult

from .affect import AffectiveLayer
from .meta_selector import MetaSelector
from .model import SelfModel


@dataclass
class UnifiedCognitiveLoop:
    selector: AdaptiveModelSelector
    presence_monitor: PresenceMonitor | None = None
    self_model: SelfModel = field(default_factory=SelfModel)
    affective_layer: AffectiveLayer = field(default_factory=AffectiveLayer)
    meta_selector: MetaSelector = field(default_factory=MetaSelector)

    def run_task(
        self,
        selection_input: Dict[str, Any],
        identity: Optional[Dict[str, Any]] = None,
        *,
        capu_features: Optional[Dict[str, float]] = None,
        state_after: str | None = None,
    ) -> Dict[str, Any]:
        strategy = self.meta_selector.choose_strategy(self.self_model, self.affective_layer)
        decision_context: SelectionResult = self.selector.select(
            selection_input,
            identity or {},
            strategy=strategy,
        )

        if self.presence_monitor is not None:
            self.self_model.update_from_lpi(self.presence_monitor.current_state.state)
        if state_after:
            self.self_model.update_from_state(state_after)
        if capu_features:
            self.self_model.update_from_capu(capu_features)

        self.affective_layer.update(self.self_model)

        return {
            "strategy": strategy,
            "selection": decision_context,
            "predicted_state": self.self_model.predict_next_state(),
        }
