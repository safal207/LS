from __future__ import annotations

from typing import Any
import copy
import time


class Retrospective:
    """
    Phase 12 - Retrospective Engine (Layer E)

    Collects and summarizes telemetry from Mode A.
    Does not modify behavior.
    """

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []

    def snapshot(self, stats: dict[str, Any]) -> None:
        self.history.append({
            "timestamp": time.time(),
            "stats": copy.deepcopy(stats),
        })

    def summarize(self) -> dict[str, Any]:
        summary = {
            "total_snapshots": len(self.history),
            "heuristics_usage": self._aggregate_heuristics(),
            "cache": self._aggregate_cache(),
            "load": self._aggregate_load(),
            "input": self._aggregate_input(),
        }
        summary["cache_insights"] = self._cache_insights(summary)
        return summary

    def reset(self) -> None:
        self.history.clear()

    def _aggregate_heuristics(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for entry in self.history:
            stats = entry.get("stats", {})
            heuristics = stats.get("heuristics", {})
            for key, value in heuristics.items():
                totals[key] = totals.get(key, 0) + int(value)
        return totals

    def _aggregate_cache(self) -> dict[str, float | int]:
        hits = 0
        misses = 0
        for entry in self.history:
            stats = entry.get("stats", {})
            hits += int(stats.get("cache_hits", 0))
            misses += int(stats.get("cache_misses", 0))
        total = hits + misses
        hit_rate = (hits / total) if total else 0.0
        return {
            "hits": hits,
            "misses": misses,
            "total": total,
            "hit_rate": hit_rate,
        }

    def _aggregate_load(self) -> dict[str, int]:
        load_shed = 0
        by_source: dict[str, int] = {}
        for entry in self.history:
            stats = entry.get("stats", {})
            load_shed += int(stats.get("load_shed", 0))
            sources = stats.get("load_shed_by_source", {})
            for key, value in sources.items():
                by_source[key] = by_source.get(key, 0) + int(value)
        return {
            "load_shed": load_shed,
            "load_shed_by_source": by_source,
        }

    def _aggregate_input(self) -> dict[str, Any]:
        count = 0
        total = 0
        min_len: int | None = None
        max_len: int | None = None
        buckets = {
            "0-4": 0,
            "5-10": 0,
            "11-50": 0,
            "51-100": 0,
            "101+": 0,
        }

        for entry in self.history:
            stats = entry.get("stats", {})
            input_stats = stats.get("input_length", {})
            count += int(input_stats.get("count", 0))
            total += int(input_stats.get("total", 0))
            if input_stats.get("min") is not None:
                value = int(input_stats["min"])
                min_len = value if min_len is None else min(min_len, value)
            if input_stats.get("max") is not None:
                value = int(input_stats["max"])
                max_len = value if max_len is None else max(max_len, value)
            input_buckets = input_stats.get("buckets", {})
            for key in buckets:
                buckets[key] += int(input_buckets.get(key, 0))

        avg = (total / count) if count else 0.0
        return {
            "count": count,
            "total": total,
            "min": min_len,
            "max": max_len,
            "avg": avg,
            "buckets": buckets,
        }

    def _cache_insights(self, summary: dict[str, Any]) -> dict[str, Any]:
        cache = summary.get("cache", {})
        load = summary.get("load", {})
        heuristics = summary.get("heuristics_usage", {})

        hits = float(cache.get("hits", 0))
        misses = float(cache.get("misses", 0))
        total = hits + misses

        repeat_rate = (hits / total) if total else 0.0
        hit_ratio = repeat_rate

        load_shed_saved = 0
        reasons: list[str] = []

        if total == 0:
            reasons.append("no cache data available yet")
        else:
            if repeat_rate >= 0.5:
                reasons.append("cache hit rate above 50%")
            elif repeat_rate > 0:
                reasons.append("cache hit rate above 0%")

            if hits >= 10:
                reasons.append("high repetition of simple queries")

            if load.get("load_shed", 0) and hits > 0:
                reasons.append("cache mitigates load-shed events")

            if heuristics.get("temporal_lookup", 0) and hits > 0:
                reasons.append("temporal lookups frequently requested")

        return {
            "repeat_rate": repeat_rate,
            "hit_ratio": hit_ratio,
            "load_shed_saved": load_shed_saved,
            "reasons": reasons,
        }
