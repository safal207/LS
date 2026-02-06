from __future__ import annotations

import time
from typing import Any

from .bias import FieldBias

from .registry import FieldRegistry
from .state import FieldNodeState, FieldState


class FieldAdapter:
    def __init__(self, node_id: str, registry: FieldRegistry) -> None:
        self.node_id = node_id
        self.registry = registry

    def publish_from_ls(self, snapshot: dict[str, Any]) -> None:
        orientation = self._coerce_float_dict(snapshot.get("orientation"))
        confidence = self._coerce_float_dict(snapshot.get("confidence"))
        trajectory = self._coerce_float_dict(snapshot.get("trajectory"))
        node_state = FieldNodeState(
            node_id=self.node_id,
            timestamp=time.time(),
            orientation=orientation,
            confidence=confidence,
            trajectory=trajectory,
        )
        self.registry.update_node(node_state)

    def pull_field_state(self) -> FieldState:
        return self.registry.get_state()

    def pull_field_metrics(self) -> dict[str, float]:
        return self.registry.get_state().metrics or {}

    def compute_field_bias(self, bias: FieldBias) -> dict[str, float]:
        metrics = self.pull_field_metrics()
        return bias.compute_bias(metrics)

    @staticmethod
    def _coerce_float_dict(value: Any) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, float] = {}
        for key, item in value.items():
            try:
                result[str(key)] = float(item)
            except (TypeError, ValueError):
                continue
        return result
