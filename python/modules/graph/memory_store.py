# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from .decay import ResonanceDecayConfig, effective_score, prune_expired
from .evolve import RouteSnapshot
from .models import (
    MemoryCase,
    RelationalEdge,
    RelationalFieldSnapshot,
    RelationalSelf,
    ResonanceKnowledgeUnit,
)

_STORE_LOCKS: dict[str, threading.RLock] = {}
_STORE_LOCKS_GUARD = threading.Lock()


def _get_store_lock(path: Path) -> threading.RLock:
    """Return a process-wide reentrant lock for a concrete store path."""
    key = str(path.resolve())
    with _STORE_LOCKS_GUARD:
        lock = _STORE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _STORE_LOCKS[key] = lock
        return lock


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryGraphStore:
    """Simple JSONL-backed storage for cooperative network memory.

    This is intentionally minimal for MVP-1. It keeps the persistence layer
    cheap and inspectable before introducing a heavier graph store.
    """

    def __init__(self, path: str | Path = "data/graph_memory/cases.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = _get_store_lock(self.path)

    def list_cases(self) -> list[MemoryCase]:
        with self._lock:
            if not self.path.exists():
                return []
            cases: list[MemoryCase] = []
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    cases.append(MemoryCase.from_dict(json.loads(line)))
            return cases

    def get_case(self, case_id: str) -> Optional[MemoryCase]:
        for case in self.list_cases():
            if case.case_id == case_id:
                return case
        return None

    def save_case(self, case: MemoryCase) -> MemoryCase:
        with self._lock:
            cases = self.list_cases()
            if not case.case_id:
                case.case_id = str(uuid4())
            if not case.created_at:
                case.created_at = _utc_now()
            updated = False
            for index, existing in enumerate(cases):
                if existing.case_id == case.case_id:
                    cases[index] = case
                    updated = True
                    break
            if not updated:
                cases.append(case)
            self._write_cases(cases)
            return case

    def remember(
        self,
        *,
        question_text: str,
        clean_text: str,
        answer_text: str,
        intent: str | None = None,
        why: str | None = None,
        thread_context: str | None = None,
        answer_quality: dict | None = None,
        contributors: list[dict] | None = None,
    ) -> MemoryCase:
        case = MemoryCase(
            case_id=str(uuid4()),
            question_text=question_text,
            clean_text=clean_text,
            intent=intent,
            why=why,
            thread_context=thread_context,
            answer_text=answer_text,
            answer_quality=dict(answer_quality or {}),
            contributors=list(contributors or []),
            created_at=_utc_now(),
        )
        return self.save_case(case)

    def mark_reused(self, case_id: str) -> Optional[MemoryCase]:
        case = self.get_case(case_id)
        if case is None:
            return None
        case.reuse_count += 1
        case.last_reused_at = _utc_now()
        return self.save_case(case)

    def _atomic_write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass

    def _atomic_write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass

    def _write_cases(self, cases: list[MemoryCase]) -> None:
        self._atomic_write_jsonl(
            self.path,
            [case.to_dict() for case in cases],
        )

    # ──────────────────────────────────────────────────────────────
    # ResonanceKnowledgeUnit — хранилище проверенных маршрутов мышления
    # ──────────────────────────────────────────────────────────────

    def _resonance_path(self) -> Path:
        """Отдельный JSONL-файл для когнитивных маршрутов."""
        return self.path.with_name("resonance_units.jsonl")

    def store_resonance_unit(
        self,
        unit: ResonanceKnowledgeUnit,
    ) -> ResonanceKnowledgeUnit:
        """Сохраняет или обновляет единицу проверенного когнитивного маршрута."""
        with self._lock:
            units = self._load_resonance_units()

            if not unit.unit_id:
                unit.unit_id = str(uuid4())
            if not unit.timestamp:
                unit.timestamp = _utc_now()

            updated = False
            for i, existing in enumerate(units):
                if existing.unit_id == unit.unit_id:
                    units[i] = unit
                    updated = True
                    break

            if not updated:
                units.append(unit)

            self._write_resonance_units(units)
            return unit

    def list_resonance_units(self) -> list[ResonanceKnowledgeUnit]:
        return self._load_resonance_units()

    def find_relevant_units(
        self,
        *,
        intent: str | None = None,
        why: str | None = None,
        goal_vector: list[float] | None = None,
        query_text: str | None = None,
        top_k: int = 5,
        decay_config: ResonanceDecayConfig | None = None,
    ) -> list[ResonanceKnowledgeUnit]:
        """Heuristic retrieval for confirmed cognitive routes.

        Only live (non-expired) units are considered.  Match scores are
        weighted by effective_score so recently confirmed, high-resonance
        units rank above stale ones that happen to share keywords.
        """
        config = decay_config or ResonanceDecayConfig()
        # Search only the live set — expired units must not pollute hints.
        units = prune_expired(self._load_resonance_units(), config)
        scored: list[tuple[ResonanceKnowledgeUnit, float]] = []

        top_k = max(1, int(top_k or 1))
        _ = goal_vector  # TODO: add cosine similarity in follow-up
        query_text_lower = query_text.lower() if query_text else None

        for u in units:
            match_score = 0.0

            if intent and u.intent and intent.lower() in u.intent.lower():
                match_score += 0.4
            if why and u.why and why.lower() in u.why.lower():
                match_score += 0.4

            query_match = (
                query_text_lower
                and u.source_question
                and query_text_lower in u.source_question.lower()
            )
            if query_match:
                match_score += 0.3

            if match_score > 0.0:
                # Multiply by decay weight: fresh/confirmed units rank higher.
                decay_weight = effective_score(u, config)
                scored.append((u, match_score * decay_weight))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [u for u, _ in scored[:top_k]]

    def list_live_resonance_units(
        self,
        config: ResonanceDecayConfig | None = None,
    ) -> list[ResonanceKnowledgeUnit]:
        """Return only non-expired resonance units after applying decay.

        Units whose effective score has dropped below ``config.floor_score``
        are excluded.  The returned list is not sorted — call
        :func:`~graph.decay.apply_decay` directly if you need ordering.

        Args:
            config: Decay configuration; uses defaults when omitted.
        """
        decay_config = config or ResonanceDecayConfig()
        return prune_expired(self._load_resonance_units(), decay_config)

    def get_resonance_snapshot(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> list[ResonanceKnowledgeUnit]:
        """Return latest resonance units above score threshold.

        Snapshot is ordered by freshness (newest first) and bounded by ``top_k``.
        """
        units = self._load_resonance_units()
        threshold = float(min_resonance_score)
        limit = max(1, int(top_k or 1))
        filtered = [u for u in units if float(u.resonance_score) > threshold]
        filtered.sort(key=lambda unit: str(unit.timestamp or ""), reverse=True)
        return filtered[:limit]

    def confirm_resonance_unit(self, unit_id: str) -> Optional[ResonanceKnowledgeUnit]:
        """Refresh a unit's timestamp, resetting its decay clock.

        Called when a resonance unit is successfully reused in a live route —
        confirmation is the memory equivalent of a half-life extension.

        Returns the updated unit, or None if not found.
        """
        with self._lock:
            units = self._load_resonance_units()
            for unit in units:
                if unit.unit_id == unit_id:
                    unit.timestamp = _utc_now()
                    self._write_resonance_units(units)
                    return unit
        return None

    def _load_resonance_units(self) -> list[ResonanceKnowledgeUnit]:
        with self._lock:
            path = self._resonance_path()
            if not path.exists():
                return []

            units: list[ResonanceKnowledgeUnit] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        units.append(ResonanceKnowledgeUnit.from_dict(json.loads(line)))
            return units

    def _write_resonance_units(self, units: list[ResonanceKnowledgeUnit]) -> None:
        """MVP-only storage.

        Atomic file replace is used; graph-store backend can come later.
        """
        path = self._resonance_path()
        self._atomic_write_jsonl(
            path,
            [unit.to_dict() for unit in units],
        )

    # ──────────────────────────────────────────────────────────────
    # RelationalEdge — typed links between ResonanceKnowledgeUnits
    # ──────────────────────────────────────────────────────────────

    def store_relational_edge(
        self,
        unit_id: str,
        edge: RelationalEdge,
    ) -> Optional[ResonanceKnowledgeUnit]:
        """Append a relational edge to a unit's relations list.

        Duplicate edges (same edge_id) are silently ignored.  Returns the
        updated unit, or None when unit_id is not found.
        """
        with self._lock:
            units = self._load_resonance_units()
            for unit in units:
                if unit.unit_id == unit_id:
                    existing_ids = {
                        r.get("edge_id")
                        for r in unit.relations
                        if isinstance(r, dict)
                    }
                    edge_dict = edge.to_dict()
                    if edge_dict.get("edge_id") not in existing_ids:
                        unit.relations.append(edge_dict)
                        self._write_resonance_units(units)
                    return unit
        return None

    def update_relational_edge_strength(
        self,
        *,
        unit_id: str,
        edge_id: str,
        feedback_polarity: float | None = None,
        resonance_score: float | None = None,
        review_decision: str | None = None,
        incident_published: bool = False,
        learning_rate: float = 0.2,
        max_step: float = 0.2,
    ) -> dict[str, Any] | None:
        """Adapt a relation edge strength from cycle outcomes.

        The update is bounded and deterministic:
        - combined signal in ``[-1, 1]`` from feedback/resonance/outcome,
        - delta limited by ``max_step``,
        - resulting strength clamped to ``[0, 1]``.
        """

        def _clamp(value: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, value))

        with self._lock:
            units = self._load_resonance_units()
            for unit in units:
                if unit.unit_id != unit_id:
                    continue
                for relation in unit.relations:
                    if not isinstance(relation, dict) or str(relation.get("edge_id") or "") != edge_id:
                        continue

                    current_strength = _clamp(float(relation.get("strength", 0.5) or 0.5), 0.0, 1.0)

                    feedback_signal = _clamp(float(feedback_polarity or 0.0), -1.0, 1.0)
                    resonance_signal = 0.0
                    if resonance_score is not None:
                        # map 0..1 resonance to -1..1 learning direction
                        resonance_signal = _clamp((float(resonance_score) - 0.5) * 2.0, -1.0, 1.0)

                    decision = str(review_decision or "").strip().lower()
                    outcome_signal = 0.0
                    if decision == "approved":
                        outcome_signal += 0.5
                    elif decision in {"rejected", "closed"}:
                        outcome_signal -= 0.5
                    if bool(incident_published):
                        outcome_signal -= 0.8

                    combined_signal = _clamp(
                        (0.45 * feedback_signal) + (0.25 * resonance_signal) + (0.30 * outcome_signal),
                        -1.0,
                        1.0,
                    )
                    bounded_step = _clamp(float(learning_rate or 0.0), 0.0, 1.0) * combined_signal
                    delta = _clamp(bounded_step, -abs(float(max_step or 0.0)), abs(float(max_step or 0.0)))

                    new_strength = _clamp(current_strength + delta, 0.0, 1.0)
                    relation["strength"] = round(new_strength, 4)

                    metadata = relation.get("metadata")
                    if not isinstance(metadata, dict):
                        metadata = {}
                    updates = metadata.get("strength_updates")
                    if not isinstance(updates, list):
                        updates = []
                    updates.append(
                        {
                            "timestamp": _utc_now(),
                            "strength_before": round(current_strength, 4),
                            "strength_after": round(new_strength, 4),
                            "delta": round(delta, 4),
                            "learning_rate": round(float(learning_rate or 0.0), 4),
                            "combined_signal": round(combined_signal, 4),
                            "feedback_signal": round(feedback_signal, 4),
                            "resonance_signal": round(resonance_signal, 4),
                            "outcome_signal": round(outcome_signal, 4),
                            "review_decision": decision,
                            "incident_published": bool(incident_published),
                        }
                    )
                    metadata["strength_updates"] = updates
                    relation["metadata"] = metadata

                    self._write_resonance_units(units)
                    return relation
                return None
        return None

    def get_relational_graph(
        self,
        unit_id: str,
        depth: int = 2,
    ) -> dict[str, Any]:
        """BFS subgraph of relational edges starting from *unit_id*.

        Returns a dict with:
        - ``root_unit_id`` — starting node
        - ``nodes`` — list of unit summaries visited during BFS
        - ``edges`` — list of edge dicts traversed
        - ``depth`` — max hop depth requested
        """
        all_units = {u.unit_id: u for u in self._load_resonance_units()}
        if unit_id not in all_units:
            return {"root_unit_id": unit_id, "nodes": [], "edges": [], "depth": depth}

        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(unit_id, 0)]
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)

            unit = all_units.get(current_id)
            if unit is None:
                continue

            nodes.append({
                "unit_id": unit.unit_id,
                "source_question": unit.source_question,
                "intent": unit.intent,
                "resonance_score": unit.resonance_score,
                "depth": current_depth,
            })

            # Only traverse edges when we have depth budget left.
            # If current_depth == depth we include this node in the result but
            # must NOT enqueue its neighbours — that would produce edges that
            # point to nodes outside the requested depth, leaving dangling refs.
            # We also skip edges whose target does not exist in the store so
            # the returned graph never contains refs to ghost units.
            if current_depth < depth:
                for rel in unit.relations:
                    if not isinstance(rel, dict):
                        continue
                    target_id = rel.get("target_unit_id")
                    if target_id and target_id not in visited and target_id in all_units:
                        edges.append({
                            "source": current_id,
                            "target": target_id,
                            "relation_type": rel.get("relation_type"),
                            "strength": rel.get("strength"),
                            "edge_id": rel.get("edge_id"),
                        })
                        queue.append((target_id, current_depth + 1))

        return {
            "root_unit_id": unit_id,
            "nodes": nodes,
            "edges": edges,
            "depth": depth,
        }

    def get_resonance_with_relations(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Snapshot of top resonance units together with their relation lists.

        Each item in the returned list is a dict with two keys:
        - ``unit`` — full ``ResonanceKnowledgeUnit.to_dict()`` payload
        - ``relations`` — list of ``RelationalEdge`` dicts attached to the unit
        """
        units = self.get_resonance_snapshot(
            top_k=top_k,
            min_resonance_score=min_resonance_score,
        )
        return [
            {"unit": u.to_dict(), "relations": list(u.relations)}
            for u in units
        ]

    # ──────────────────────────────────────────────────────────────
    # RelationalFieldSnapshot — observational interaction field layer
    # ──────────────────────────────────────────────────────────────

    def _relational_snapshots_path(self) -> Path:
        return self.path.with_name("relational_field_snapshots.jsonl")

    def store_relational_snapshot(
        self,
        snapshot: RelationalFieldSnapshot,
    ) -> RelationalFieldSnapshot:
        with self._lock:
            snapshots = self._load_relational_snapshots()
            if not snapshot.field_id:
                snapshot.field_id = str(uuid4())
            if not snapshot.timestamp:
                snapshot.timestamp = _utc_now()
            snapshots.append(snapshot)
            self._write_relational_snapshots(snapshots)
            return snapshot

    def list_relational_snapshots(self) -> list[RelationalFieldSnapshot]:
        return self._load_relational_snapshots()

    def _load_relational_snapshots(self) -> list[RelationalFieldSnapshot]:
        with self._lock:
            path = self._relational_snapshots_path()
            if not path.exists():
                return []

            snapshots: list[RelationalFieldSnapshot] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        snapshots.append(
                            RelationalFieldSnapshot.from_dict(json.loads(line))
                        )
            return snapshots

    def _write_relational_snapshots(
        self,
        snapshots: list[RelationalFieldSnapshot],
    ) -> None:
        self._atomic_write_jsonl(
            self._relational_snapshots_path(),
            [snapshot.to_dict() for snapshot in snapshots],
        )

    # ──────────────────────────────────────────────────────────────
    # RouteSnapshot — versioned evolved route candidates
    # ──────────────────────────────────────────────────────────────

    def _route_snapshots_path(self) -> Path:
        return self.path.with_name("route_snapshots.jsonl")

    # ──────────────────────────────────────────────────────────────
    # RelationalSelf — holistic self-state snapshot
    # ──────────────────────────────────────────────────────────────

    def _relational_self_path(self) -> Path:
        return self.path.with_name("relational_self.json")

    def _coherence_history_path(self) -> Path:
        return self.path.with_name("relational_self_coherence_history.jsonl")

    def _constitution_history_path(self) -> Path:
        return self.path.with_name("relational_self_constitution_history.jsonl")

    def _council_action_history_path(self) -> Path:
        return self.path.with_name("relational_self_council_actions.jsonl")

    def get_relational_self(self) -> RelationalSelf:
        with self._lock:
            path = self._relational_self_path()
            if not path.exists():
                return RelationalSelf()
            payload = json.loads(path.read_text(encoding="utf-8"))
            return RelationalSelf.from_dict(dict(payload))

    def get_coherence_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            path = self._coherence_history_path()
            if not path.exists():
                return []
            rows: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(dict(json.loads(line)))
            return rows[-max(1, int(limit or 1)) :]

    def store_constitution_evaluation(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            history = self.get_constitution_history(limit=500)
            payload = dict(row)
            payload.setdefault("timestamp", _utc_now())
            history.append(payload)
            self._atomic_write_jsonl(self._constitution_history_path(), history[-500:])
            return payload

    def get_constitution_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            path = self._constitution_history_path()
            if not path.exists():
                return []
            rows: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(dict(json.loads(line)))
                    except Exception:
                        # Robustness: skip malformed rows instead of failing reads.
                        continue
            return rows[-max(1, int(limit or 1)) :]

    def store_council_action_record(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            history = self.get_council_action_history(limit=1000)
            payload = dict(row)
            payload.setdefault("timestamp", _utc_now())
            history.append(payload)
            self._atomic_write_jsonl(self._council_action_history_path(), history[-1000:])
            return payload

    def get_council_action_history(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            path = self._council_action_history_path()
            if not path.exists():
                return []
            rows: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(dict(json.loads(line)))
                    except Exception:
                        # Robustness: skip malformed rows instead of failing reads.
                        continue
            return rows[-max(1, int(limit or 1)) :]

    def rollback_council_action(self, *, action_id: str) -> dict[str, Any]:
        with self._lock:
            action = next(
                (row for row in reversed(self.get_council_action_history(limit=1000)) if str(row.get("action_id")) == str(action_id)),
                None,
            )
            if not action:
                return {"rolled_back": False, "reason": "action_not_found", "action_id": action_id}
            if bool(action.get("rolled_back", False)):
                return {"rolled_back": False, "reason": "already_rolled_back", "action_id": action_id}
            if bool(action.get("partially_rolled_back", False)) or str(action.get("rollback_scope") or "") == "partial":
                return {
                    "rolled_back": False,
                    "reason": "already_partially_rolled_back",
                    "action_id": action_id,
                    "partially_rolled_back": True,
                    "rollback_scope": "partial",
                }

            updates = list(action.get("updates") or [])
            restored = 0
            unsupported_updates = 0
            units = self._load_resonance_units()
            for update in updates:
                update_type = str(update.get("update_type") or "")
                if update_type != "relation_strength":
                    unsupported_updates += 1
                    continue
                unit_id = str(update.get("unit_id") or "")
                target_id = str(update.get("target_unit_id") or "")
                before = float(update.get("before", 0.5) or 0.5)
                for unit in units:
                    if unit.unit_id != unit_id:
                        continue
                    for rel in list(unit.relations or []):
                        if (
                            isinstance(rel, dict)
                            and str(rel.get("target_unit_id") or "") == target_id
                            and str(rel.get("relation_type") or "") == "reinforces"
                        ):
                            rel["strength"] = round(before, 4)
                            restored += 1
            self._write_resonance_units(units)

            history = self.get_council_action_history(limit=1000)
            is_partial = unsupported_updates > 0
            has_effect = restored > 0
            rolled_back_flag = not is_partial
            rollback_scope = "partial" if is_partial else "full"
            rollback_reason = (
                "partial_rollback_unsupported_updates"
                if is_partial
                else ("rollback_applied" if has_effect else "no_supported_updates")
            )
            for row in history:
                if str(row.get("action_id")) == str(action_id):
                    row["rolled_back"] = rolled_back_flag
                    row["partially_rolled_back"] = is_partial
                    row["rollback_scope"] = rollback_scope
                    row["rollback_reason"] = rollback_reason
                    row["rolled_back_at"] = _utc_now()
                    break
            self._atomic_write_jsonl(self._council_action_history_path(), history[-1000:])
            refreshed = self.update_self_from_cycle(
                cycle_id=str(action_id),
                source="council_action_rollback",
            )
            # Phase 2.4: record emotional memory for the rollback event
            # Rollback = repair attempt; write under same lock to stay consistent
            try:
                self.update_emotional_memory_from_cycle(
                    cycle_id=str(action_id),
                    source="council",
                    coherence_score=float(refreshed.self_coherence_score or 0.0),
                    rollback_present=True,
                    relational_context=[str(action_id)],
                )
            except Exception as exc:  # emotional memory must never block rollback
                logger.debug("Rollback emotional memory update skipped: %s", exc)
            return {
                "rolled_back": rolled_back_flag,
                "partially_rolled_back": is_partial,
                "rollback_scope": rollback_scope,
                "action_id": action_id,
                "restored_updates": restored,
                "unsupported_updates": unsupported_updates,
                "relational_self_snapshot_id": refreshed.snapshot_id,
                "relational_self_coherence_score": float(refreshed.self_coherence_score or 0.0),
                "reason": rollback_reason,
            }

    def get_self_metrics_snapshot(self, *, window: int = 100) -> dict[str, Any]:
        with self._lock:
            latest_self = self.get_relational_self()
            constitution_rows = self.get_constitution_history(limit=max(1, int(window or 1)))
            action_rows = self.get_council_action_history(limit=max(1, int(window or 1)))

            violation_count = sum(
                1
                for row in constitution_rows
                if isinstance(row.get("constitution"), dict)
                and not bool(row["constitution"].get("passed", True))
            )
            auto_apply_total = sum(
                1
                for row in constitution_rows
                if isinstance(row.get("policy_decision"), dict)
                and row["policy_decision"].get("reason")
                in {
                    "safe_for_auto_apply",
                    "constitution_escalate_violation",
                    "constitution_violation",
                    "blocked_by_preservation",
                }
            )
            auto_apply_allowed = sum(
                1
                for row in constitution_rows
                if isinstance(row.get("policy_decision"), dict)
                and bool(row["policy_decision"].get("allow_auto_apply", False))
            )
            rollback_count = sum(1 for row in action_rows if bool(row.get("rolled_back", False)))
            recovery_windows: list[int] = []
            last_violation_index: int | None = None
            for idx, row in enumerate(constitution_rows):
                constitution = row.get("constitution")
                if not isinstance(constitution, dict):
                    continue
                passed = bool(constitution.get("passed", True))
                if not passed:
                    if last_violation_index is None:
                        last_violation_index = idx
                elif passed and last_violation_index is not None:
                    recovery_windows.append(idx - last_violation_index)
                    last_violation_index = None

            return {
                "window": max(1, int(window or 1)),
                "self_coherence_score": float(latest_self.self_coherence_score or 0.0),
                "constitution_violation_count": violation_count,
                "auto_action_apply_rate": round((auto_apply_allowed / auto_apply_total), 4) if auto_apply_total else 0.0,
                "rollback_rate": round((rollback_count / len(action_rows)), 4) if action_rows else 0.0,
                "mean_recovery_cycles": round(sum(recovery_windows) / len(recovery_windows), 4) if recovery_windows else 0.0,
                "action_count": len(action_rows),
                "constitution_eval_count": len(constitution_rows),
            }

    def update_self_from_cycle(
        self,
        *,
        cycle_id: str | None = None,
        source: str = "care_cycle",
        recent_window: int = 25,
        omni_insight: dict[str, Any] | None = None,
    ) -> RelationalSelf:
        with self._lock:
            units = self.list_resonance_units()
            units.sort(key=lambda unit: str(unit.timestamp or ""), reverse=True)
            selected = units[: max(3, int(recent_window or 3))]

            core_nodes = [
                {
                    "unit_id": u.unit_id,
                    "intent": u.intent,
                    "resonance_score": float(u.resonance_score),
                    "alignment_score": float(u.alignment_score),
                    "timestamp": u.timestamp,
                }
                for u in selected
            ]
            unit_map = {u.unit_id: u for u in selected}
            core_edges: list[dict[str, Any]] = []
            for unit in selected:
                for relation in list(unit.relations or []):
                    if not isinstance(relation, dict):
                        continue
                    target = str(relation.get("target_unit_id") or "")
                    if target in unit_map:
                        core_edges.append(
                            {
                                "source_unit_id": unit.unit_id,
                                "target_unit_id": target,
                                "relation_type": str(relation.get("relation_type") or "reinforces"),
                                "strength": float(relation.get("strength", 0.0) or 0.0),
                            }
                        )

            if omni_insight and str(omni_insight.get("signal") or "").lower() in {"fatigue", "tired"}:
                top_unit_id = selected[0].unit_id if selected else ""
                if top_unit_id:
                    core_edges.append(
                        {
                            "source_unit_id": top_unit_id,
                            "target_unit_id": top_unit_id,
                            "relation_type": "emotional_link",
                            "strength": 0.55,
                        }
                    )

            avg_resonance = (
                sum(float(u.resonance_score) for u in selected) / len(selected)
                if selected
                else 0.0
            )
            avg_alignment = (
                sum(float(u.alignment_score) for u in selected) / len(selected)
                if selected
                else 0.0
            )
            contradiction_penalty = sum(
                0.2
                for edge in core_edges
                if str(edge.get("relation_type") or "") == "contradicts"
                and float(edge.get("strength", 0.0) or 0.0) >= 0.7
            )
            coherence = max(
                0.0,
                min(1.0, (0.45 * avg_resonance) + (0.45 * avg_alignment) - contradiction_penalty),
            )
            identity_vector = [
                round(avg_resonance, 4),
                round(avg_alignment, 4),
                round(min(1.0, len(core_nodes) / 10.0), 4),
                round(min(1.0, len(core_edges) / 15.0), 4),
            ]

            current = self.get_relational_self()
            previous_score = float(current.self_coherence_score or 0.0)
            updated_at = _utc_now()
            history_item = {
                "timestamp": updated_at,
                "cycle_id": cycle_id,
                "source": source,
                "coherence_before": round(previous_score, 4),
                "coherence_after": round(coherence, 4),
                "delta": round(coherence - previous_score, 4),
                "node_count": len(core_nodes),
                "edge_count": len(core_edges),
            }
            change_history = (list(current.change_history or []) + [history_item])[-25:]
            snapshot = RelationalSelf(
                snapshot_id=current.snapshot_id or str(uuid4()),
                schema_version=current.schema_version or "1.0",
                created_at=current.created_at or updated_at,
                updated_at=updated_at,
                core_nodes=core_nodes,
                core_edges=core_edges,
                self_coherence_score=round(coherence, 4),
                self_identity_vector=identity_vector,
                change_history=change_history,
                metadata={
                    "schema_version": "1.0",
                    "updated_by": source,
                    "cycle_id": cycle_id,
                    "omni_insight": dict(omni_insight or {}),
                },
                # Phase 2.4: carry over emotional_summary so cognitive updates
                # don't wipe the emotional layer (additive field preservation)
                emotional_summary=dict(current.emotional_summary or {}),
            )

            self._atomic_write_json(self._relational_self_path(), snapshot.to_dict())
            history_rows = self.get_coherence_history(limit=500)
            history_rows.append(
                {
                    "timestamp": updated_at,
                    "coherence_score": round(coherence, 4),
                    "source": source,
                    "cycle_id": cycle_id,
                }
            )
            self._atomic_write_jsonl(self._coherence_history_path(), history_rows[-500:])
            return snapshot

    def store_route_snapshot(self, snapshot: RouteSnapshot) -> RouteSnapshot:
        """Upsert a RouteSnapshot keyed by snapshot_id (latest version wins)."""
        with self._lock:
            snapshots = self._load_route_snapshots()
            updated = False
            for i, existing in enumerate(snapshots):
                if existing.snapshot_id == snapshot.snapshot_id:
                    snapshots[i] = snapshot
                    updated = True
                    break
            if not updated:
                snapshots.append(snapshot)
            self._atomic_write_jsonl(
                self._route_snapshots_path(),
                [s.to_dict() for s in snapshots],
            )
            return snapshot

    def list_route_snapshots(self) -> list[RouteSnapshot]:
        return self._load_route_snapshots()

    def list_promoted_snapshots(self) -> list[RouteSnapshot]:
        """Return only promoted, non-rolled-back snapshots."""
        return [
            s for s in self._load_route_snapshots()
            if s.promoted and not s.rolled_back
        ]

    def get_route_snapshot(self, snapshot_id: str) -> Optional[RouteSnapshot]:
        for s in self._load_route_snapshots():
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def _load_route_snapshots(self) -> list[RouteSnapshot]:
        with self._lock:
            path = self._route_snapshots_path()
            if not path.exists():
                return []
            snapshots: list[RouteSnapshot] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        snapshots.append(RouteSnapshot.from_dict(json.loads(line)))
            return snapshots

    # ──────────────────────────────────────────────────────────────
    # Phase 2.4 — Emotional Memory & Emotional Arc persistence
    # ──────────────────────────────────────────────────────────────

    _EMOTIONAL_MEMORY_CAP = 1000
    _EMOTIONAL_ARC_CAP = 1000

    def _emotional_memory_path(self) -> Path:
        return self.path.with_name("relational_self_emotional_memory.jsonl")

    def _emotional_arc_path(self) -> Path:
        return self.path.with_name("relational_self_emotional_arc.jsonl")

    def _read_emotional_memory_rows_unlocked(self) -> list[dict[str, Any]]:
        """Read, parse, and decay-refresh all emotional memory rows.

        Does NOT acquire the lock — caller must hold ``self._lock`` or be the
        sole writer.  Malformed rows are silently skipped.
        """
        from modules.cognition.emotional_memory import EmotionalBondingEngine
        engine = EmotionalBondingEngine()
        path = self._emotional_memory_path()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = dict(json.loads(line))
                    ts = str(row.get("timestamp") or "")
                    if ts:
                        row["temporal_decay"] = engine.compute_temporal_decay(ts)
                    rows.append(row)
                except Exception:
                    continue
        return rows

    def _read_emotional_arc_rows_unlocked(self) -> list[dict[str, Any]]:
        """Read and parse all emotional arc rows.

        Does NOT acquire the lock — caller must hold ``self._lock`` or be the
        sole writer.  Malformed rows are silently skipped.
        """
        path = self._emotional_arc_path()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(dict(json.loads(line)))
                except Exception:
                    continue
        return rows

    def store_emotional_memory_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Append a new EmotionalMemoryEntry dict with retention cap.

        Malformed existing rows are skipped; cap is enforced on write.
        """
        with self._lock:
            rows = self._read_emotional_memory_rows_unlocked()
            payload = dict(entry)
            payload.setdefault("timestamp", _utc_now())
            rows.append(payload)
            self._atomic_write_jsonl(self._emotional_memory_path(), rows[-self._EMOTIONAL_MEMORY_CAP:])
            return payload

    def get_emotional_memory(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent emotional memory entries.

        Malformed rows are skipped (robustness requirement).
        Temporal decay is recalculated on read for freshness accuracy.
        """
        with self._lock:
            rows = self._read_emotional_memory_rows_unlocked()
            return rows[-max(1, int(limit or 1)):]

    def get_emotional_arc(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return the emotional bond arc trajectory (most recent *limit* points).

        Malformed rows are skipped.
        """
        with self._lock:
            rows = self._read_emotional_arc_rows_unlocked()
            return rows[-max(1, int(limit or 1)):]

    def _append_emotional_arc_point(self, point: dict[str, Any]) -> None:
        """Append one arc point; enforces retention cap atomically.

        Holds the store lock for the full read-modify-write cycle so concurrent
        writers cannot interleave and drop arc points.
        """
        with self._lock:
            arc = self._read_emotional_arc_rows_unlocked()
            arc.append(point)
            self._atomic_write_jsonl(self._emotional_arc_path(), arc[-self._EMOTIONAL_ARC_CAP:])

    def update_emotional_memory_from_cycle(
        self,
        *,
        cycle_id: str | None = None,
        source: str = "care_cycle",
        resonance_score: float = 0.0,
        alignment_score: float = 0.0,
        coherence_score: float | None = None,
        omni_signal: str | None = None,
        user_feedback: str | None = None,
        rollback_present: bool = False,
        contradiction_spike: bool = False,
        policy_blocked: bool = False,
        reflective_context: bool = False,
        relational_context: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build, store, and aggregate a new emotional memory entry from cycle signals.

        Also appends a new arc point and updates the emotional_summary on the
        stored RelationalSelf snapshot (additive — never clobbers other fields).

        Returns the newly created EmotionalMemoryEntry dict.
        """
        from modules.cognition.emotional_memory import EmotionalBondingEngine

        with self._lock:
            engine = EmotionalBondingEngine()

            # Determine coherence from current self if not provided
            if coherence_score is None:
                coherence_score = float(self.get_relational_self().self_coherence_score or 0.0)

            # ── Single read pass — avoids redundant file I/O ─────────────────
            rows = self._read_emotional_memory_rows_unlocked()
            arc = self._read_emotional_arc_rows_unlocked()

            current_bond = float((rows[-1].get("bond_strength") or 0.0) if rows else 0.0)

            entry_dict = engine.build_entry(
                resonance_score=resonance_score,
                alignment_score=alignment_score,
                coherence_score=coherence_score,
                omni_signal=omni_signal,
                user_feedback=user_feedback,
                rollback_present=rollback_present,
                contradiction_spike=contradiction_spike,
                policy_blocked=policy_blocked,
                reflective_context=reflective_context,
                current_bond=current_bond,
                trigger_source=source,
                relational_context=relational_context,
                cycle_id=cycle_id,
            )
            entry_dict.setdefault("timestamp", _utc_now())

            # ── Single write pass — memory + arc atomically ───────────────────
            rows.append(entry_dict)
            self._atomic_write_jsonl(
                self._emotional_memory_path(),
                rows[-self._EMOTIONAL_MEMORY_CAP:],
            )

            arc_point = {
                "timestamp": entry_dict["timestamp"],
                "bond_strength": entry_dict["bond_strength"],
                "dominant_tone": entry_dict["emotional_tone"],
                "valence": entry_dict["valence"],
                "source": source,
                "cycle_id": cycle_id,
            }
            arc.append(arc_point)
            self._atomic_write_jsonl(
                self._emotional_arc_path(),
                arc[-self._EMOTIONAL_ARC_CAP:],
            )

            # ── Aggregate from in-memory data — no extra reads ────────────────
            all_entries = rows[-self._EMOTIONAL_MEMORY_CAP:]
            all_arc = arc[-self._EMOTIONAL_ARC_CAP:]
            new_bond = float(entry_dict.get("bond_strength") or 0.0)
            summary = engine.aggregate_emotional_summary(all_entries, new_bond, all_arc)
            self._update_emotional_summary_in_self(summary)

            return entry_dict

    def _update_emotional_summary_in_self(self, summary: dict[str, Any]) -> None:
        """Overwrite only the emotional_summary field in the stored RelationalSelf.

        All other RelationalSelf fields are preserved unchanged.
        """
        current = self.get_relational_self()
        current.emotional_summary = dict(summary)
        self._atomic_write_json(self._relational_self_path(), current.to_dict())
