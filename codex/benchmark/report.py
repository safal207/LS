from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


LOWER_IS_BETTER = {
    "loadtimems",
    "firsttokenlatency_ms",
    "transcriptionlatencyms",
    "processinglatencyms",
    "realtimefactor",
}


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    model_type: str
    metrics: Dict[str, float]
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "type": self.model_type,
            "metrics": dict(self.metrics),
            "success": self.success,
            "timestamp": self.timestamp,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BenchmarkResult":
        return cls(
            model=payload["model"],
            model_type=payload.get("type", "unknown"),
            metrics=dict(payload.get("metrics", {})),
            success=payload.get("success", True),
            metadata=dict(payload.get("metadata", {})),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


class BenchmarkReport:
    def __init__(self, results_dir: str | Path) -> None:
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def save(self, result: BenchmarkResult) -> Path:
        path = self.results_dir / f"{result.model}.json"
        path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load(self, model: str) -> BenchmarkResult:
        path = self.results_dir / f"{model}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return BenchmarkResult.from_dict(payload)

    def load_all(self) -> List[BenchmarkResult]:
        results: List[BenchmarkResult] = []
        for path in sorted(self.results_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            results.append(BenchmarkResult.from_dict(payload))
        return results

    def list_models(self) -> List[str]:
        return [path.stem for path in sorted(self.results_dir.glob("*.json"))]

    def compare(self, metric: str, results: Iterable[BenchmarkResult]) -> List[Dict[str, Any]]:
        rows = []
        for result in results:
            if not result.success:
                continue
            if metric not in result.metrics:
                continue
            rows.append({"model": result.model, "value": result.metrics[metric]})
        reverse = metric not in LOWER_IS_BETTER
        return sorted(rows, key=lambda row: row["value"], reverse=reverse)

    def model_report(self, model: str) -> Dict[str, Any]:
        result = self.load(model)
        all_results = self.load_all()
        model_type = result.model_type
        if model_type == "llm":
            metrics = [
                "tokenspersecond",
                "firsttokenlatency_ms",
                "loadtimems",
                "peakrammb",
                "peakvrammb",
                "stability_score",
            ]
        elif model_type == "stt":
            metrics = [
                "transcriptionlatencyms",
                "realtimefactor",
                "loadtimems",
                "peakrammb",
            ]
        else:
            metrics = ["processinglatencyms", "loadtimems"]
        comparisons = {metric: self.compare(metric, all_results) for metric in metrics}
        return {"result": result.to_dict(), "comparisons": comparisons}
