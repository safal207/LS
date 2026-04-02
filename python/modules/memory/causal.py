from __future__ import annotations

import itertools
from typing import Any

try:
    from ghostgpt_core import RustCausalMemory  # type: ignore
except Exception:  # fallback in environments without rust extension
    RustCausalMemory = None


class _PythonFallbackCausalMemory:
    def __init__(self) -> None:
        self._id_counter = itertools.count(start=1)
        self._nodes: dict[str, dict[str, Any]] = {}
        self._axis_map = {
            "Customer": -1.0,
            "Consumer": -0.33,
            "Execution": 0.33,
            "Stability": 1.0,
        }

    def add_intent(self, layer: str, content: str) -> str:
        if layer != "Customer":
            raise ValueError("add_intent supports only Customer layer")
        node_id = str(next(self._id_counter))
        self._nodes[node_id] = {
            "content": content,
            "layer": layer,
            "parent": None,
            "resonance": 1.0,
            "axis_position": self._axis_map["Customer"],
        }
        return node_id

    def transition_down(self, parent_id: str, new_content: str, new_layer: str) -> str:
        parent = self._nodes[parent_id]
        parent_tokens = set(parent["content"].lower().split())
        child_tokens = set(new_content.lower().split())
        overlap = len(parent_tokens & child_tokens)
        union = max(len(parent_tokens | child_tokens), 1)
        score = overlap / union
        if score < 0.35:
            raise ValueError("ResonanceError")
        node_id = str(next(self._id_counter))
        self._nodes[node_id] = {
            "content": new_content,
            "layer": new_layer,
            "parent": parent_id,
            "resonance": score,
            "axis_position": self._axis_map.get(new_layer, 0.0),
        }
        return node_id

    def check_resonance(self, node_id: str) -> float:
        node = self._nodes[node_id]
        return float(node["resonance"])

    def stabilize(self, node_id: str) -> bool:
        node = self._nodes[node_id]
        return node["layer"] == "Stability" and float(node["resonance"]) >= 0.35

    def get_axis_position(self, node_id: str) -> float:
        node = self._nodes[node_id]
        return float(node["axis_position"])


class CausalMemory:
    def __init__(self) -> None:
        self._rust = RustCausalMemory() if RustCausalMemory is not None else _PythonFallbackCausalMemory()

    def add_intent(self, content: str) -> str:
        return self._rust.add_intent("Customer", content)

    def transition_down(self, node_id: str, new_content: str, new_layer: str) -> str:
        return self._rust.transition_down(node_id, new_content, new_layer)

    def check_resonance(self, node_id: str) -> float:
        return float(self._rust.check_resonance(node_id))

    def stabilize(self, node_id: str) -> bool:
        return bool(self._rust.stabilize(node_id))

    def get_axis_position(self, node_id: str) -> float:
        return float(self._rust.get_axis_position(node_id))
