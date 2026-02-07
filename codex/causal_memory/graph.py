from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .store import MemoryRecord


@dataclass(frozen=True)
class CausalEdge:
    cause: str
    effect: str
    weight: float
    count: int


class CausalGraph:
    def __init__(self) -> None:
        self._edges: Dict[Tuple[str, str], Dict[str, float]] = {}

    def add_edge(self, cause: str, effect: str, weight: float = 1.0) -> None:
        key = (cause, effect)
        entry = self._edges.get(key)
        if entry is None:
            self._edges[key] = {"weight": float(weight), "count": 1}
            return
        count = int(entry["count"])
        current = float(entry["weight"])
        entry["weight"] = (current * count + weight) / (count + 1)
        entry["count"] = count + 1

    def observe(self, record: MemoryRecord) -> None:
        conditions = list(self._conditions_from_record(record))
        model_label = f"model:{record.model}"
        outcome = "success" if record.success else "failure"
        outcome_label = f"{outcome}:{record.model}"
        for condition in conditions:
            self.add_edge(condition, outcome_label, weight=1.0)
            self.add_edge(condition, model_label, weight=0.5)
        if record.error:
            self.add_edge(f"error:{record.error}", outcome_label, weight=1.0)

    def get_downstream(self, cause: str) -> List[CausalEdge]:
        edges = []
        for (edge_cause, effect), data in self._edges.items():
            if edge_cause != cause:
                continue
            edges.append(
                CausalEdge(cause=edge_cause, effect=effect, weight=data["weight"], count=int(data["count"]))
            )
        return edges

    def get_upstream(self, effect: str) -> List[CausalEdge]:
        edges = []
        for (cause, edge_effect), data in self._edges.items():
            if edge_effect != effect:
                continue
            edges.append(CausalEdge(cause=cause, effect=edge_effect, weight=data["weight"], count=int(data["count"])))
        return edges

    def edges(self) -> List[CausalEdge]:
        return [
            CausalEdge(cause=cause, effect=effect, weight=data["weight"], count=int(data["count"]))
            for (cause, effect), data in self._edges.items()
        ]

    @staticmethod
    def _conditions_from_record(record: MemoryRecord) -> Iterable[str]:
        hardware = record.hardware
        metrics = record.metrics

        ram_gb = hardware.get("ram_gb")
        if isinstance(ram_gb, (int, float)) and ram_gb < 8:
            yield "ram<8gb"

        vram_gb = hardware.get("vram_gb")
        if isinstance(vram_gb, (int, float)) and vram_gb < 4:
            yield "vram<4gb"

        tps = metrics.get("tokenspersecond")
        if isinstance(tps, (int, float)) and tps < 5:
            yield "tps<5"

        first_token = metrics.get("firsttokenlatency_ms")
        if isinstance(first_token, (int, float)) and first_token > 1500:
            yield "firsttoken>1500ms"

        rtf = metrics.get("realtimefactor")
        if isinstance(rtf, (int, float)) and rtf > 1.0:
            yield "rtf>1"

        logits_margin = metrics.get("logits_confidence_margin")
        if isinstance(logits_margin, (int, float)) and logits_margin < 0.1:
            yield "low_confidence_logits"

        attention_entropy = metrics.get("avg_attention_entropy")
        if isinstance(attention_entropy, (int, float)) and attention_entropy > 5.0:
            yield "diffuse_attention"

        segments_count = metrics.get("segments_count")
        if isinstance(segments_count, (int, float)) and segments_count > 25:
            yield "stt_segments>25"
