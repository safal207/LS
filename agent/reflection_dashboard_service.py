"""Service layer for Reflection Dashboard backend/frontend contract."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from .reflection import ReflectionPipeline
from .reflection_actions import ReflectionActionHandler


class ReflectionDashboardService:
    """Expose reflection dashboard data and actions through a stable contract."""

    def __init__(self, pipeline: ReflectionPipeline):
        self.pipeline = pipeline
        self.action_handler = ReflectionActionHandler(self.pipeline.decision_pipeline)

    def get_dashboard_snapshot(self, recent_limit: int = 20, timeline_limit: int = 30) -> Dict[str, Any]:
        """Return memory graph, recent reflections, metrics, and heatmap data."""
        proposals = self.pipeline.generate_proposals()
        return {
            "memory_graph": self.get_memory_graph(),
            "recent_reflections": self.get_recent_reflections(limit=recent_limit),
            "metrics": self.get_metrics(proposals=proposals),
            "heatmap": self.get_heatmap_data(),
            "action_timeline": self.get_action_timeline(limit=timeline_limit),
            "proposals": proposals,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_memory_graph(self) -> Dict[str, Any]:
        """Return graph snapshot stored in cognitive state for dashboard rendering."""
        graph = self.pipeline.cognitive_state.get("memory_graph")
        if isinstance(graph, dict):
            return {
                "nodes": list(graph.get("nodes", [])),
                "edges": list(graph.get("edges", [])),
            }
        return {"nodes": [], "edges": []}

    def get_recent_reflections(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return most recent reflection records available in cognitive state."""
        reflections = self.pipeline.cognitive_state.get("recent_reflections", [])
        if not isinstance(reflections, list):
            return []
        ordered = sorted(
            [item for item in reflections if isinstance(item, dict)],
            key=lambda item: item.get("timestamp", ""),
            reverse=True,
        )
        return ordered[: max(limit, 0)]

    def get_action_timeline(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return latest operator and pipeline activities for UI timeline."""
        activity = self.pipeline.cognitive_state.get("pipeline_activity", [])
        if not isinstance(activity, list):
            return []
        valid = [item for item in activity if isinstance(item, dict)]
        ordered = sorted(valid, key=lambda item: item.get("timestamp", ""), reverse=True)
        return ordered[: max(limit, 0)]

    def get_metrics(self, proposals: Iterable[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        """Calculate baseline confidence and contradiction metrics."""
        proposal_list = list(proposals) if proposals is not None else self.pipeline.generate_proposals()

        confidences = [float(item.get("confidence", 0.0)) for item in proposal_list]
        confidence_score = sum(confidences) / len(confidences) if confidences else 0.0

        contradiction_events = self.pipeline.cognitive_state.get("reflection_contradictions", [])
        canonical = self.pipeline.cognitive_state.get("canonical_reflections", [])

        return {
            "proposal_count": len(proposal_list),
            "confidence_score": round(confidence_score, 3),
            "contradiction_count": len(contradiction_events) if isinstance(contradiction_events, list) else 0,
            "canonical_count": len(canonical) if isinstance(canonical, list) else 0,
        }

    def get_heatmap_data(self) -> List[Dict[str, Any]]:
        """Return hourly activity heatmap for dashboard trends."""
        activity = self.pipeline.cognitive_state.get("pipeline_activity", [])
        bucket: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "reject": 0, "approve": 0, "edit": 0})

        for item in activity:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("timestamp")
            action_type = str(item.get("type", "unknown"))
            hour_key = self._hour_bucket(timestamp)
            bucket[hour_key]["count"] += 1
            if action_type in {"reject", "approve", "edit"}:
                bucket[hour_key][action_type] += 1

        return [
            {
                "hour": hour,
                "count": stats["count"],
                "approve": stats["approve"],
                "reject": stats["reject"],
                "edit": stats["edit"],
            }
            for hour, stats in sorted(bucket.items())
        ]

    def approve(self, proposal: Dict[str, Any]) -> List[str]:
        """Approve and apply a reflection proposal, promoting it as canonical."""
        messages = self.action_handler.apply_selected([proposal], action="approve")
        self._append_canonical_reflection(proposal)
        self.pipeline.decision_pipeline.register_action_activity("approve", {"proposal_id": proposal.get("proposal_id")})
        return messages

    def reject(self, proposal: Dict[str, Any], reason: str | None = None) -> List[str]:
        """Reject a proposal, record contradiction, and trigger rethink marker."""
        messages = self.action_handler.reject_selected([proposal])
        self._append_contradiction(proposal, reason=reason)
        self.pipeline.cognitive_state["rethink_required"] = True
        self.pipeline.decision_pipeline.register_action_activity("reject", {"proposal_id": proposal.get("proposal_id")})
        return messages

    def edit(self, proposal: Dict[str, Any], proposed_value: Any, note: str | None = None) -> List[str]:
        """Apply an edited proposal value as a new version of the proposal."""
        version = int(proposal.get("version", 1)) + 1
        edited = dict(proposal)
        edited["proposal_id"] = f"{proposal.get('proposal_id', 'proposal')}:v{version}"
        edited["parent_proposal_id"] = proposal.get("proposal_id")
        edited["version"] = version
        edited["proposed_value"] = proposed_value
        edited["edited_at"] = datetime.now(timezone.utc).isoformat()
        if note:
            edited["edit_note"] = note

        messages = self.action_handler.apply_selected([edited], action="edit")
        self._append_reflection_version(edited)
        self.pipeline.decision_pipeline.register_action_activity(
            "edit",
            {
                "proposal_id": edited.get("proposal_id"),
                "parent_proposal_id": proposal.get("proposal_id"),
            },
        )
        return messages

    def _append_canonical_reflection(self, proposal: Dict[str, Any]) -> None:
        canonical = self.pipeline.cognitive_state.setdefault("canonical_reflections", [])
        if isinstance(canonical, list):
            canonical.append(
                {
                    "proposal_id": proposal.get("proposal_id"),
                    "change_type": proposal.get("change_type"),
                    "target": proposal.get("target"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    def _append_contradiction(self, proposal: Dict[str, Any], reason: str | None = None) -> None:
        contradictions = self.pipeline.cognitive_state.setdefault("reflection_contradictions", [])
        if isinstance(contradictions, list):
            contradictions.append(
                {
                    "proposal_id": proposal.get("proposal_id"),
                    "change_type": proposal.get("change_type"),
                    "reason": reason or "operator_reject",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    def _append_reflection_version(self, edited_proposal: Dict[str, Any]) -> None:
        versions = self.pipeline.cognitive_state.setdefault("reflection_versions", {})
        if not isinstance(versions, dict):
            return
        root_id = str(edited_proposal.get("parent_proposal_id") or edited_proposal.get("proposal_id"))
        history = versions.setdefault(root_id, [])
        if isinstance(history, list):
            history.append(edited_proposal)

    @staticmethod
    def _hour_bucket(timestamp: Any) -> str:
        if not isinstance(timestamp, str):
            return "unknown"
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            return "unknown"
        return parsed.replace(minute=0, second=0, microsecond=0).isoformat()
