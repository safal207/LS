from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

MODULES_ROOT = Path(__file__).resolve().parents[2] / "modules"
if MODULES_ROOT.exists() and str(MODULES_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULES_ROOT))

from modules.graph.path_selector import PathSelector  # noqa: E402
from modules.graph.route_stats import RouteStats, RouteStatsStore  # noqa: E402
from modules.graph.trail_updater import PathExecutionRecord, TrailUpdater  # noqa: E402


DEFAULT_BACKENDS = ["local", "gonka", "mimo"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


class TrailNetworkBridge:
    """Local-first MCP bridge for cooperative route memory.

    The bridge records route contributions and outcomes locally. It does not
    update model weights, call remote services, or grant action authority.
    """

    def __init__(
        self,
        *,
        route_store_path: str | Path | None = None,
        event_log_path: str | Path | None = None,
    ) -> None:
        self.route_store_path = Path(
            route_store_path
            or os.environ.get("GRAPH_TRAIL_STORE_PATH", "data/graph_memory/routes.json")
        )
        self.event_log_path = Path(
            event_log_path
            or os.environ.get("LS_TRAIL_MCP_EVENTS_PATH", "data/graph_memory/trail_mcp_events.jsonl")
        )
        self.store = RouteStatsStore(self.route_store_path)

    def recommend_route(self, args: dict[str, Any]) -> dict[str, Any]:
        graph_mode = str(args.get("graph_mode") or args.get("task_type") or "pr_review").strip() or "pr_review"
        available_backends = [
            str(item)
            for item in (_safe_list(args.get("available_backends")) or DEFAULT_BACKENDS)
            if str(item).strip()
        ] or list(DEFAULT_BACKENDS)
        default_backend = str(args.get("default_backend") or available_backends[0])
        exploration_rate = _safe_float(args.get("exploration_rate"), 0.0)

        selector = PathSelector(
            self.store,
            exploration_rate=max(0.0, min(1.0, exploration_rate)),
        )
        decision = selector.choose_route(
            graph_mode=graph_mode,
            available_backends=available_backends,
            default_backend=default_backend,
            intent=str(args.get("intent") or "") or None,
            why_tag=str(args.get("why_tag") or "") or None,
            force_exploration=bool(args.get("force_exploration", False)),
            goal_style=str(args.get("goal_style") or "") or None,
            strategy_bias=str(args.get("strategy_bias") or "") or None,
        )
        route = self.store.get_route(decision.route_key) or RouteStats(route_key=decision.route_key)
        return {
            "tool": "ls_trail_recommend_route",
            "status": "recommended",
            "task_type": str(args.get("task_type") or graph_mode),
            "available_backends": available_backends,
            "route": decision.to_dict(),
            "route_stats": self._route_payload(route),
            "network_learning": "read_existing_route_memory_only",
            "human_authority_required": True,
            "last_updated": _utc_now(),
        }

    def submit_contribution(self, args: dict[str, Any]) -> dict[str, Any]:
        route_key = str(args.get("route_key") or "").strip()
        actor = str(args.get("actor") or "").strip()
        role = str(args.get("role") or "").strip()
        if not route_key:
            raise ValueError("route_key is required")
        if not actor:
            raise ValueError("actor is required")
        if not role:
            raise ValueError("role is required")

        event = {
            "event_id": f"trail-event-{uuid4()}",
            "event_type": "contribution_submitted",
            "timestamp": _utc_now(),
            "task_id": str(args.get("task_id") or ""),
            "route_key": route_key,
            "actor": actor,
            "role": role,
            "contribution_type": str(args.get("contribution_type") or "agent_output"),
            "evidence_refs": [str(item) for item in _safe_list(args.get("evidence_refs"))],
            "quality": dict(args.get("quality") or {}),
            "note": str(args.get("note") or ""),
        }
        self._append_event(event)
        return {
            "tool": "ls_trail_submit_contribution",
            "accepted": True,
            "status": "recorded_pending_outcome",
            "event": event,
            "does_not_update_route_score": True,
            "next_step": "call ls_trail_record_outcome after evidence, human, or CI feedback exists",
        }

    def validate_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        claims = _safe_list(args.get("claims") or args.get("findings"))
        min_coverage = _safe_float(args.get("min_coverage"), 0.7)
        rows: list[dict[str, Any]] = []

        for index, raw in enumerate(claims, start=1):
            if isinstance(raw, dict):
                claim = str(raw.get("claim") or raw.get("text") or raw.get("description") or "")
                refs = [str(item) for item in _safe_list(raw.get("evidence_refs") or raw.get("sources"))]
                explicit_supported = raw.get("supported")
                supported = bool(refs) if explicit_supported is None else bool(explicit_supported)
            else:
                claim = str(raw)
                refs = []
                supported = False
            rows.append(
                {
                    "index": index,
                    "claim": claim,
                    "evidence_refs": refs,
                    "supported": supported,
                    "reason": "has_evidence" if supported else "missing_evidence",
                }
            )

        total = len(rows)
        supported_count = sum(1 for row in rows if row["supported"])
        coverage = round(supported_count / total, 4) if total else 0.0
        decision = "pass" if total and coverage >= min_coverage else "needs_evidence"
        return {
            "tool": "ls_trail_validate_evidence",
            "decision": decision,
            "total_claims": total,
            "supported_claims": supported_count,
            "unsupported_claims": total - supported_count,
            "evidence_coverage": coverage,
            "min_coverage": min_coverage,
            "claims": rows,
            "last_updated": _utc_now(),
        }

    def record_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        route_key = str(args.get("route_key") or "").strip()
        if not route_key:
            raise ValueError("route_key is required")
        if not self._has_outcome_signal(args):
            raise ValueError(
                "at least one outcome signal is required: quality, evidence_coverage, "
                "false_positive_rate, human_accepted, ci_passed, useful_findings, or unsupported_claims"
            )

        quality = self._quality_from_outcome(args)
        record = PathExecutionRecord(
            route_key=route_key,
            question_text=str(args.get("task_text") or args.get("prompt") or args.get("task_id") or ""),
            graph_mode=str(args.get("graph_mode") or route_key.split(">")[0] or "unknown"),
            selected_backend=str(args.get("selected_backend") or args.get("actor") or "cooperative"),
            quality=quality,
            latency_ms=_safe_float(args.get("latency_ms"), 0.0),
        )
        route, reward = TrailUpdater(self.store).update(record)
        event = {
            "event_id": f"trail-event-{uuid4()}",
            "event_type": "outcome_recorded",
            "timestamp": _utc_now(),
            "task_id": str(args.get("task_id") or ""),
            "route_key": route_key,
            "reward": reward,
            "quality": quality,
            "human_accepted": bool(args.get("human_accepted", False)),
            "ci_passed": args.get("ci_passed"),
        }
        self._append_event(event)
        return {
            "tool": "ls_trail_record_outcome",
            "status": "route_memory_updated",
            "reward": reward,
            "route_stats": self._route_payload(route),
            "event": event,
            "network_learning": "local_route_memory_updated",
            "human_authority_required": True,
        }

    def query_best_trails(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = max(1, int(args.get("limit", 10) or 10))
        prefix = str(args.get("route_prefix") or args.get("task_type") or "").strip()
        routes = self.store.list_routes()
        if prefix:
            routes = [route for route in routes if route.route_key.startswith(prefix)]
        payload = [self._route_payload(route) for route in routes]
        payload.sort(
            key=lambda item: (
                float(item["repeatability_score"]),
                float(item["pheromone_weight"]),
                float(item["avg_quality"]),
            ),
            reverse=True,
        )
        return {
            "tool": "ls_trail_query_best_trails",
            "route_prefix": prefix,
            "count": len(payload[:limit]),
            "routes": payload[:limit],
            "last_updated": _utc_now(),
        }

    def read_events(self, *, limit: int = 20) -> dict[str, Any]:
        safe_limit = max(1, int(limit or 20))
        events: list[dict[str, Any]] = []
        if self.event_log_path.exists():
            with self.event_log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(event, dict):
                        events.append(event)
        return {
            "resource": "trail/events",
            "path": str(self.event_log_path),
            "limit": safe_limit,
            "events": events[-safe_limit:],
            "last_updated": _utc_now(),
        }

    def _append_event(self, event: dict[str, Any]) -> None:
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _quality_from_outcome(self, args: dict[str, Any]) -> dict[str, Any]:
        quality = dict(args.get("quality") or {})
        evidence_coverage = _safe_float(args.get("evidence_coverage"), _safe_float(quality.get("relevance"), 0.5))
        false_positive_rate = _safe_float(args.get("false_positive_rate"), _safe_float(quality.get("hallucination_risk"), 0.2))
        human_score = 0.9 if bool(args.get("human_accepted", False)) else 0.5
        ci_signal = args.get("ci_passed")
        ci_score = 0.8 if ci_signal is True else 0.35 if ci_signal is False else 0.5
        useful = _safe_float(args.get("useful_findings"), 0.0)
        unsupported = _safe_float(args.get("unsupported_claims"), 0.0)
        finding_score = 0.5
        if useful or unsupported:
            finding_score = max(0.0, min(1.0, useful / max(1.0, useful + unsupported)))

        quality.setdefault("relevance", max(0.0, min(1.0, evidence_coverage)))
        quality.setdefault("thread_relevance", max(0.0, min(1.0, evidence_coverage)))
        quality.setdefault("hallucination_risk", max(0.0, min(1.0, false_positive_rate)))
        quality.setdefault("coherence", max(0.0, min(1.0, ci_score)))
        quality.setdefault("goal_alignment_score", max(0.0, min(1.0, human_score)))
        quality.setdefault(
            "overall",
            round(
                (
                    float(quality["relevance"])
                    + float(quality["thread_relevance"])
                    + float(quality["coherence"])
                    + float(quality["goal_alignment_score"])
                    + finding_score
                    + (1.0 - float(quality["hallucination_risk"]))
                )
                / 6.0,
                4,
            ),
        )
        return quality

    @staticmethod
    def _has_outcome_signal(args: dict[str, Any]) -> bool:
        quality = args.get("quality")
        if isinstance(quality, dict) and bool(quality):
            return True
        signal_keys = {
            "evidence_coverage",
            "false_positive_rate",
            "human_accepted",
            "ci_passed",
            "useful_findings",
            "unsupported_claims",
        }
        return any(key in args and args.get(key) is not None for key in signal_keys)

    def _route_payload(self, route: RouteStats) -> dict[str, Any]:
        runs = max(0, int(route.runs or 0))
        success_rate = round(float(route.successes or 0) / runs, 4) if runs else 0.0
        latency_score = max(0.0, min(1.0, 1.0 - (float(route.avg_latency_ms or 0.0) / 30000.0)))
        repeatability_score = round(
            (0.40 * float(route.avg_quality or 0.0))
            + (0.25 * float(route.avg_goal_alignment or 0.0))
            + (0.25 * success_rate)
            + (0.10 * latency_score),
            4,
        )
        payload = route.to_dict()
        payload["success_rate"] = success_rate
        payload["repeatability_score"] = repeatability_score
        return payload
