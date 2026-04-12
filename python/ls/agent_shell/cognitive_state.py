from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CognitiveStateBridge:
    """Read-only aggregation over LS cognitive state for MCP exposure."""

    def __init__(self, *, task_manager: Any) -> None:
        self._store_path = Path(
            os.environ.get("GRAPH_MEMORY_STORE_PATH", "data/graph_memory/cases.jsonl")
        )
        self._task_manager = task_manager

    def get_resonance_snapshot(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        safe_top_k = max(1, int(top_k or 1))
        safe_threshold = float(min_resonance_score)
        units = self._runtime_resonance_snapshot(
            top_k=safe_top_k,
            min_resonance_score=safe_threshold,
        )
        if units is None:
            units = self._file_resonance_snapshot(
                top_k=safe_top_k,
                min_resonance_score=safe_threshold,
            )
        return {
            "resource": "resonance/snapshot",
            "top_k": safe_top_k,
            "min_resonance_score": safe_threshold,
            "items": units,
            "last_updated": _utc_now(),
        }

    def get_cognitive_state(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        """Backward-compatible aggregate cognitive state payload for MCP tools."""
        return {
            "resource": "cognitive/state",
            "resonance_snapshot": self.get_resonance_snapshot(
                top_k=top_k,
                min_resonance_score=min_resonance_score,
            ),
            "relational_state": self.get_relational_state(
                top_k=top_k,
                min_resonance_score=min_resonance_score,
            ),
            "alignment": self.get_alignment_current(),
            "omni": self.get_omni_last_insight(),
            "last_updated": _utc_now(),
        }

    def _runtime_resonance_snapshot(
        self,
        *,
        top_k: int,
        min_resonance_score: float,
    ) -> list[dict[str, Any]] | None:
        if not hasattr(self._task_manager, "get_resonance_snapshot"):
            return None
        try:
            rows = self._task_manager.get_resonance_snapshot(
                top_k=top_k,
                min_resonance_score=min_resonance_score,
            )
        except Exception:
            logger.debug("Runtime resonance snapshot failed", exc_info=True)
            return None

        payload: list[dict[str, Any]] = []
        for row in rows or []:
            if hasattr(row, "to_dict"):
                payload.append(dict(row.to_dict()))
            elif isinstance(row, dict):
                payload.append(dict(row))
            else:
                payload.append({"value": row})
        return payload

    def _file_resonance_snapshot(
        self,
        *,
        top_k: int,
        min_resonance_score: float,
    ) -> list[dict[str, Any]]:
        path = self._store_path.with_name("resonance_units.jsonl")
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = line.strip()
                if not row:
                    continue
                try:
                    payload = dict(json.loads(row))
                except Exception:
                    logger.debug("Skipping malformed resonance JSONL row")
                    continue
                if float(payload.get("resonance_score", 0.0) or 0.0) < min_resonance_score:
                    continue
                items.append(payload)
        items.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return items[:top_k]

    def get_alignment_current(self) -> dict[str, Any]:
        if hasattr(self._task_manager, "get_alignment_current"):
            payload = dict(self._task_manager.get_alignment_current())
        else:
            payload = {
                "alignment_state": "unavailable",
                "outcomes": [],
                "softening_detected": False,
                "reason": "Alignment provider is not bound in the current runtime.",
            }

        payload["resource"] = "alignment/current"
        payload.setdefault("last_updated", _utc_now())
        return payload

    def get_omni_last_insight(self) -> dict[str, Any]:
        enabled = str(os.environ.get("QWEN_OMNI_ENABLED", "0")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if not enabled:
            return {
                "resource": "omni/last-insight",
                "enabled": False,
                "insight": None,
                "reason": "QWEN_OMNI_ENABLED is off",
                "last_updated": _utc_now(),
            }

        insight: dict[str, Any] | None = None
        if hasattr(self._task_manager, "get_omni_last_insight"):
            try:
                raw = self._task_manager.get_omni_last_insight()
                insight = dict(raw) if raw else None
            except Exception:
                logger.debug("Runtime omni insight lookup failed", exc_info=True)

        return {
            "resource": "omni/last-insight",
            "enabled": True,
            "insight": insight,
            "last_updated": _utc_now(),
        }

    def get_relational_self_summary(self) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        snapshot = store.get_relational_self().to_dict()
        return {
            "resource": "self/relational-self",
            "snapshot": snapshot,
            "last_updated": _utc_now(),
        }

    def get_coherence_history(self, *, limit: int = 30) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        rows = store.get_coherence_history(limit=int(limit))
        return {
            "resource": "self/coherence-history",
            "items": rows,
            "limit": int(limit),
            "last_updated": _utc_now(),
        }

    def get_constitution_status(self, *, limit: int = 20) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        rows = store.get_constitution_history(limit=int(limit))
        latest = rows[-1] if rows else None
        return {
            "resource": "self/constitution-status",
            "latest": latest,
            "items": rows,
            "limit": int(limit),
            "last_updated": _utc_now(),
        }

    def get_self_metrics(self, *, window: int = 100) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        metrics = store.get_self_metrics_snapshot(window=int(window))
        return {
            "resource": "self/metrics",
            "metrics": metrics,
            "last_updated": _utc_now(),
        }

    def get_action_history(self, *, limit: int = 30) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        items = store.get_council_action_history(limit=int(limit))
        return {
            "resource": "self/action-history",
            "items": items,
            "limit": int(limit),
            "last_updated": _utc_now(),
        }

    def rollback_self_action(self, *, action_id: str) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        result = store.rollback_council_action(action_id=str(action_id))
        result["resource"] = "self/rollback-action"
        result["last_updated"] = _utc_now()
        return result

    def ask_self(self, question: str) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        prompt = str(question or "").strip()
        store = MemoryGraphStore(self._store_path)
        snapshot = store.get_relational_self()
        days = 3
        match = re.search(r"(\d+)", prompt)
        if match:
            days = max(1, int(match.group(1)))
        history = store.get_coherence_history(limit=max(10, days * 12))
        if history:
            now = datetime.now(timezone.utc)
            filtered: list[dict[str, Any]] = []
            for row in history:
                timestamp = str(row.get("timestamp") or "")
                try:
                    row_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if (now - row_dt).total_seconds() <= days * 86400:
                    filtered.append(row)
            if filtered:
                history = filtered
        delta = 0.0
        if len(history) >= 2:
            delta = float(history[-1].get("coherence_score", 0.0) or 0.0) - float(
                history[0].get("coherence_score", 0.0) or 0.0
            )
        direction = "stabilized"
        if delta > 0.02:
            direction = "grew more coherent"
        elif delta < -0.02:
            direction = "lost coherence"

        top_drivers = sorted(
            list(snapshot.change_history or []),
            key=lambda row: abs(float(row.get("delta", 0.0) or 0.0)),
            reverse=True,
        )[:3]
        driver_summary = [
            {
                "cycle_id": row.get("cycle_id"),
                "delta": float(row.get("delta", 0.0) or 0.0),
                "source": row.get("source"),
            }
            for row in top_drivers
        ]
        constitution_rows = store.get_constitution_history(limit=10)
        action_rows = store.get_council_action_history(limit=10)
        causal_trace: list[dict[str, Any]] = []
        prev_node_id: str | None = None
        for row in history[-3:]:
            node_id = f"coherence:{row.get('cycle_id') or row.get('timestamp')}"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "coherence_event",
                    "timestamp": row.get("timestamp"),
                    "coherence_score": row.get("coherence_score"),
                    "cycle_id": row.get("cycle_id"),
                    "confidence": 0.85,
                    "linked_from": prev_node_id,
                }
            )
            prev_node_id = node_id
        if driver_summary:
            node_id = "relation_shift:top_drivers"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "relation_shift",
                    "drivers": driver_summary,
                    "confidence": 0.78,
                    "linked_from": prev_node_id,
                }
            )
            prev_node_id = node_id
        if constitution_rows:
            latest_const = constitution_rows[-1]
            node_id = f"policy:{latest_const.get('cycle_id') or 'latest'}"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "constitution_state",
                    "cycle_id": latest_const.get("cycle_id"),
                    "passed": bool((latest_const.get("constitution") or {}).get("passed", True)),
                    "blocked": bool(latest_const.get("blocked", False)),
                    "policy_decision": dict(latest_const.get("policy_decision") or {}),
                    "confidence": 0.9,
                    "linked_from": prev_node_id,
                }
            )
            prev_node_id = node_id
        if action_rows:
            latest_action = action_rows[-1]
            node_id = f"action:{latest_action.get('action_id') or 'latest'}"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "applied_action",
                    "action_id": latest_action.get("action_id"),
                    "action": latest_action.get("action"),
                    "rolled_back": bool(latest_action.get("rolled_back", False)),
                    "action_effect": "reverted" if bool(latest_action.get("rolled_back", False)) else "applied",
                    "confidence": 0.88,
                    "linked_from": prev_node_id,
                }
            )

        return {
            "resource": "self/ask-self",
            "question": prompt,
            "answer": (
                f"Over the last {days} day(s) I {direction}. "
                f"Current coherence is {float(snapshot.self_coherence_score or 0.0):.2f}."
            ),
            "coherence_delta": round(delta, 4),
            "coherence_now": float(snapshot.self_coherence_score or 0.0),
            "top_change_drivers": driver_summary,
            "causal_trace": causal_trace,
            "last_updated": _utc_now(),
        }

    def get_relational_graph(
        self,
        unit_id: str,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Return a BFS relational subgraph centred on *unit_id*.

        Reads directly from the JSONL store so the result is always current
        even when the runtime hasn't exposed a live accessor.
        """
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        graph = store.get_relational_graph(unit_id=str(unit_id), depth=int(depth))
        graph["resource"] = "resonance/relational-graph"
        graph["last_updated"] = _utc_now()
        return graph

    def get_relational_state(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        """Combined snapshot: top resonance units plus their relational edges."""
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        items = store.get_resonance_with_relations(
            top_k=int(top_k),
            min_resonance_score=float(min_resonance_score),
        )
        return {
            "resource": "cognitive/relational-state",
            "top_k": int(top_k),
            "min_resonance_score": float(min_resonance_score),
            "items": items,
            "last_updated": _utc_now(),
        }

    def ask_relational_question(
        self,
        *,
        source_unit_id: str,
        target_unit_id: str,
    ) -> dict[str, Any]:
        """Explain why two units are connected, if an edge exists."""
        from modules.graph.memory_store import MemoryGraphStore

        source_id = str(source_unit_id or "")
        target_id = str(target_unit_id or "")
        store = MemoryGraphStore(self._store_path)
        graph = store.get_relational_graph(source_id, depth=1)
        direct_edge = next(
            (
                edge
                for edge in list(graph.get("edges") or [])
                if str(edge.get("source") or "") == source_id
                and str(edge.get("target") or "") == target_id
            ),
            None,
        )
        if direct_edge is None:
            reverse_graph = store.get_relational_graph(target_id, depth=1)
            reverse_edge = next(
                (
                    edge
                    for edge in list(reverse_graph.get("edges") or [])
                    if str(edge.get("source") or "") == target_id
                    and str(edge.get("target") or "") == source_id
                ),
                None,
            )
            if reverse_edge is not None:
                return {
                    "resource": "cognitive/relational-why",
                    "linked": True,
                    "direction": "reverse",
                    "source_unit_id": source_id,
                    "target_unit_id": target_id,
                    "relation_type": str(reverse_edge.get("relation_type") or "unknown"),
                    "strength": float(reverse_edge.get("strength", 0.0) or 0.0),
                    "explanation": "Units are connected, but the stored edge points in the reverse direction.",
                    "last_updated": _utc_now(),
                }
            return {
                "resource": "cognitive/relational-why",
                "linked": False,
                "source_unit_id": source_id,
                "target_unit_id": target_id,
                "explanation": "No direct relation edge is currently stored between these units.",
                "last_updated": _utc_now(),
            }

        relation_type = str(direct_edge.get("relation_type") or "unknown")
        strength = float(direct_edge.get("strength", 0.0) or 0.0)
        return {
            "resource": "cognitive/relational-why",
            "linked": True,
            "direction": "forward",
            "source_unit_id": source_id,
            "target_unit_id": target_id,
            "relation_type": relation_type,
            "strength": strength,
            "explanation": (
                f"Stored edge indicates '{relation_type}' with strength {strength:.2f} "
                "from source to target."
            ),
            "last_updated": _utc_now(),
        }

    def suggest_new_relation(
        self,
        *,
        source_unit_id: str,
        target_unit_id: str,
        relation_type: str = "reinforces",
        strength: float = 0.5,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        """Create a human-suggested relation edge (idempotent by target+type)."""
        from modules.graph.memory_store import MemoryGraphStore
        from modules.graph.models import RelationalEdge

        source_id = str(source_unit_id or "")
        target_id = str(target_unit_id or "")
        store = MemoryGraphStore(self._store_path)
        source_unit = next(
            (unit for unit in store.list_resonance_units() if unit.unit_id == source_id),
            None,
        )
        if source_unit is None:
            return {
                "resource": "cognitive/relational-suggestion",
                "accepted": False,
                "reason": "source_not_found",
                "source_unit_id": source_id,
                "target_unit_id": target_id,
                "last_updated": _utc_now(),
            }
        existing = next(
            (
                rel
                for rel in list(source_unit.relations or [])
                if isinstance(rel, dict)
                and str(rel.get("target_unit_id") or "") == target_id
                and str(rel.get("relation_type") or "") == str(relation_type or "reinforces")
            ),
            None,
        )
        if existing is not None:
            return {
                "resource": "cognitive/relational-suggestion",
                "accepted": True,
                "created": False,
                "reason": "duplicate_existing_relation",
                "edge": existing,
                "source_unit_id": source_id,
                "target_unit_id": target_id,
                "last_updated": _utc_now(),
            }

        edge = RelationalEdge(
            target_unit_id=target_id,
            relation_type=str(relation_type or "reinforces"),
            strength=max(0.0, min(1.0, float(strength or 0.5))),
            metadata={
                "suggested_via": "mcp",
                "rationale": str(rationale or ""),
                "suggested_at": _utc_now(),
            },
        )
        updated = store.store_relational_edge(source_id, edge)
        return {
            "resource": "cognitive/relational-suggestion",
            "accepted": updated is not None,
            "created": updated is not None,
            "source_unit_id": source_id,
            "target_unit_id": target_id,
            "edge": edge.to_dict(),
            "last_updated": _utc_now(),
        }

    # NOTE: get_cognitive_state is intentionally defined near the top of this class.
