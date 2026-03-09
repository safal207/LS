"""Reflection pipeline wrappers for UI/operator workflows."""

from __future__ import annotations

from typing import Any, Dict, List

from .decision_pipeline import DecisionPipeline


class ReflectionPipeline:
    """Thin facade around DecisionPipeline reflection methods."""

    def __init__(self, decision_pipeline: DecisionPipeline, state_path: str = "reflection_state.json"):
        self.decision_pipeline = decision_pipeline
        self.state_path = state_path

    @classmethod
    def load_state(cls, path: str = "reflection_state.json") -> "ReflectionPipeline":
        return cls(DecisionPipeline.load_state(path), state_path=path)

    def generate_proposals(self) -> List[Dict[str, Any]]:
        return self.decision_pipeline.reflect_and_propose()

    def save_state(self) -> None:
        self.decision_pipeline.save_state(self.state_path)

    @property
    def cognitive_state(self) -> Dict[str, Any]:
        return self.decision_pipeline.cognitive_state
