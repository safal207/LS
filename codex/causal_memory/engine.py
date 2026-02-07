from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .graph import CausalGraph
from .store import MemoryStore


@dataclass(frozen=True)
class ModelScore:
    model: str
    score: float
    success_rate: float
    observations: int


class AdaptiveEngine:
    def __init__(self, store: MemoryStore, graph: CausalGraph) -> None:
        self.store = store
        self.graph = graph

    def rank_models(self, models: Iterable[str], context: Dict[str, object] | None = None) -> List[ModelScore]:
        context = dict(context or {})
        conditions = list(self._conditions_from_context(context))
        scores: List[ModelScore] = []
        for model in models:
            success_rate, observations = self._success_rate(model)
            penalty = self._penalty_for_conditions(model, conditions)
            score = max(0.0, success_rate - penalty)
            scores.append(
                ModelScore(
                    model=model,
                    score=round(score, 4),
                    success_rate=round(success_rate, 4),
                    observations=observations,
                )
            )
        return sorted(scores, key=lambda item: item.score, reverse=True)

    def recommend(self, models: Iterable[str], context: Dict[str, object] | None = None, top_k: int = 3) -> List[str]:
        ranked = self.rank_models(models, context=context)
        return [entry.model for entry in ranked[:top_k]]

    def _success_rate(self, model: str) -> Tuple[float, int]:
        records = list(self.store.filter(model=model))
        if not records:
            return (0.0, 0)
        successes = sum(1 for record in records if record.success)
        return (successes / len(records), len(records))

    def _penalty_for_conditions(self, model: str, conditions: List[str]) -> float:
        penalty = 0.0
        failure_label = f"failure:{model}"
        for condition in conditions:
            for edge in self.graph.get_downstream(condition):
                if edge.effect == failure_label:
                    penalty += edge.weight * 0.2
        return min(1.0, penalty)

    @staticmethod
    def _conditions_from_context(context: Dict[str, object]) -> Iterable[str]:
        ram_gb = context.get("ram_gb")
        if isinstance(ram_gb, (int, float)) and ram_gb < 8:
            yield "ram<8gb"

        vram_gb = context.get("vram_gb")
        if isinstance(vram_gb, (int, float)) and vram_gb < 4:
            yield "vram<4gb"
