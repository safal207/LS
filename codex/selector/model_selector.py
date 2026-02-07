from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from codex.benchmark.report import LOWER_IS_BETTER, BenchmarkReport, BenchmarkResult
from codex.hardware.capabilities import HardwareCapabilities
from codex.hardware.profiler import HardwareProfiler
from codex.registry.model_config import ModelConfig
from codex.registry.model_registry import ModelRegistry


TASK_PROFILES = {
    "realtime_interview": {
        "priority": "latency",
        "types": {"llm"},
        "preferred": ["phi3-mini-4k", "qwen2.5-1.5b", "llama3.2-3b"],
    },
    "deep_analysis": {
        "priority": "quality",
        "types": {"llm"},
        "preferred": ["llama3.2-3b", "qwen2.5-1.5b"],
    },
    "offline_stt": {
        "priority": "memory",
        "types": {"stt"},
        "preferred": ["whisper-small-int8", "whisper-medium-int8"],
    },
}


PRIORITY_METRICS = {
    "latency": ["firsttokenlatency_ms", "tokenspersecond", "loadtimems"],
    "quality": ["stability_score", "tokenspersecond"],
    "memory": ["peakrammb", "peakvrammb", "loadtimems"],
}


@dataclass(frozen=True)
class SelectionResult:
    task: str
    priority: str
    selected_model: str
    reason: str
    candidates: List[str]

    def to_dict(self) -> Dict[str, str | List[str]]:
        return {
            "task": self.task,
            "priority": self.priority,
            "selected_model": self.selected_model,
            "reason": self.reason,
            "candidates": list(self.candidates),
        }


class AdaptiveModelSelector:
    def __init__(
        self,
        registry: ModelRegistry,
        profiler: HardwareProfiler,
        benchmark_report: BenchmarkReport | None = None,
    ) -> None:
        self.registry = registry
        self.profiler = profiler
        self.benchmark_report = benchmark_report

    def pick(self, task: str, priority: str | None = None) -> SelectionResult:
        profile = self.profiler.collect()
        capabilities = HardwareCapabilities(profile)

        task_profile = TASK_PROFILES.get(task, {})
        task_priority = priority or task_profile.get("priority", "latency")
        preferred = task_profile.get("preferred", [])
        allowed_types = task_profile.get("types")

        models = self._load_model_configs()
        if allowed_types:
            models = [model for model in models if model.type in allowed_types]

        if preferred:
            preferred_models = [model for model in models if model.name in preferred]
            if preferred_models:
                models = preferred_models

        supported = [model for model in models if capabilities.supports_model(model)]
        if not supported:
            raise ValueError("No compatible models found for the current hardware.")

        benchmark_results = self._load_benchmarks()
        scored = self._score_models(supported, benchmark_results, task_priority)
        selected = scored[0]
        reason = self._build_reason(selected, benchmark_results, task_priority)
        return SelectionResult(
            task=task,
            priority=task_priority,
            selected_model=selected.name,
            reason=reason,
            candidates=[model.name for model in supported],
        )

    def _load_model_configs(self) -> List[ModelConfig]:
        models: List[ModelConfig] = []
        for name in self.registry.list_models():
            config = self.registry.info(name)
            models.append(ModelConfig.from_dict(name, config))
        return models

    def _load_benchmarks(self) -> Dict[str, BenchmarkResult]:
        if not self.benchmark_report:
            return {}
        return {result.model: result for result in self.benchmark_report.load_all()}

    def _score_models(
        self,
        models: Iterable[ModelConfig],
        benchmarks: Dict[str, BenchmarkResult],
        priority: str,
    ) -> List[ModelConfig]:
        metrics = PRIORITY_METRICS.get(priority, PRIORITY_METRICS["latency"])
        model_list = list(models)
        metric_values = self._metric_values(model_list, benchmarks, metrics)

        def rank_score(model: ModelConfig) -> float:
            score = 0.0
            for metric in metrics:
                values = metric_values.get(metric, {})
                if not values:
                    score += len(model_list)
                    continue
                ordered = sorted(
                    values.items(),
                    key=lambda item: item[1],
                    reverse=metric not in LOWER_IS_BETTER,
                )
                rank = next((idx for idx, (name, _) in enumerate(ordered) if name == model.name), len(model_list))
                score += rank
            return score

        return sorted(model_list, key=rank_score)

    def _metric_values(
        self,
        models: Iterable[ModelConfig],
        benchmarks: Dict[str, BenchmarkResult],
        metrics: Iterable[str],
    ) -> Dict[str, Dict[str, float]]:
        values: Dict[str, Dict[str, float]] = {metric: {} for metric in metrics}
        for model in models:
            result = benchmarks.get(model.name)
            if not result or not result.success:
                continue
            for metric in metrics:
                metric_value = result.metrics.get(metric)
                if metric_value is not None:
                    values[metric][model.name] = metric_value
        return values

    def _build_reason(
        self,
        model: ModelConfig,
        benchmarks: Dict[str, BenchmarkResult],
        priority: str,
    ) -> str:
        result = benchmarks.get(model.name)
        if not result:
            return "Selected based on hardware compatibility and registry defaults."
        metrics = PRIORITY_METRICS.get(priority, [])
        highlights = []
        for metric in metrics:
            if metric in result.metrics:
                highlights.append(f"{metric}={result.metrics[metric]}")
        if not highlights:
            return "Selected based on available benchmark data."
        return f"Best match for {priority} with " + ", ".join(highlights)
