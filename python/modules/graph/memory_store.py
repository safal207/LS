# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .decay import ResonanceDecayConfig, effective_score, prune_expired
from .evolve import RouteSnapshot
from .models import MemoryCase, RelationalFieldSnapshot, ResonanceKnowledgeUnit

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


def _clamp_unit_interval(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def build_relational_edge_update_preview(
    *,
    strength_before: float,
    review_decision: str | None = None,
    incident_published: bool = False,
    receiver_resonance_score: float | None = None,
    relational_coherence: float | None = None,
) -> dict[str, Any]:
    """Return a deterministic, bounded preview for relation-edge learning.

    Day 1 skeleton only: this computes the shape and update rule we expect to
    persist later, without mutating any long-lived relation graph yet.
    """

    strength_before = round(_clamp_unit_interval(strength_before), 4)
    strength_after = strength_before
    reason_codes: list[str] = []

    normalized_decision = str(review_decision or "").strip().lower()
    if normalized_decision in {"approved", "approve"}:
        strength_after += 0.08
        reason_codes.append("approved_review")
    elif normalized_decision in {"rejected", "reject"}:
        strength_after -= 0.12
        reason_codes.append("rejected_review")
    elif normalized_decision == "closed":
        strength_after -= 0.06
        reason_codes.append("closed_without_approval")

    if incident_published:
        strength_after -= 0.15
        reason_codes.append("incident_published")

    if receiver_resonance_score is not None:
        resonance = _clamp_unit_interval(receiver_resonance_score)
        if resonance >= 0.7:
            strength_after += 0.05
            reason_codes.append("high_receiver_resonance")
        elif resonance <= 0.35:
            strength_after -= 0.05
            reason_codes.append("low_receiver_resonance")

    coherence = None
    review_attention_required = False
    route_guidance = "continue_current_route"
    if relational_coherence is not None:
        coherence = round(_clamp_unit_interval(relational_coherence), 4)
        if coherence <= 0.35:
            strength_after -= 0.08
            review_attention_required = True
            route_guidance = "validate_current_route"
            reason_codes.append("low_relational_coherence")
        elif coherence >= 0.7:
            route_guidance = "continue_current_route"

    strength_after = round(_clamp_unit_interval(strength_after), 4)
    applied_delta = round(strength_after - strength_before, 4)
    if not reason_codes:
        reason_codes.append("no_signal")

    return {
        "strength_before": strength_before,
        "strength_after": strength_after,
        "applied_delta": applied_delta,
        "reason_codes": reason_codes,
        "relational_coherence": coherence,
        "review_attention_required": review_attention_required,
        "route_guidance": route_guidance,
    }


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

    def _relational_edge_updates_path(self) -> Path:
        return self.path.with_name("relational_edge_updates.jsonl")

    def preview_relational_edge_update(
        self,
        *,
        strength_before: float,
        review_decision: str | None = None,
        incident_published: bool = False,
        receiver_resonance_score: float | None = None,
        relational_coherence: float | None = None,
    ) -> dict[str, Any]:
        return build_relational_edge_update_preview(
            strength_before=strength_before,
            review_decision=review_decision,
            incident_published=incident_published,
            receiver_resonance_score=receiver_resonance_score,
            relational_coherence=relational_coherence,
        )

    def store_relational_edge_update(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            updates = self._load_relational_edge_updates()
            record = dict(payload)
            record["timestamp"] = str(record.get("timestamp") or _utc_now())
            updates.append(record)
            self._write_relational_edge_updates(updates)
            return record

    def list_relational_edge_updates(self) -> list[dict[str, Any]]:
        return self._load_relational_edge_updates()

    def get_latest_relational_edge_update(
        self,
        *,
        pattern_key: str,
        selected_route: str,
    ) -> dict[str, Any] | None:
        normalized_pattern = str(pattern_key or "").strip()
        normalized_route = str(selected_route or "").strip()
        if not normalized_pattern or not normalized_route:
            return None

        latest: dict[str, Any] | None = None
        for update in self._load_relational_edge_updates():
            if (
                str(update.get("pattern_key") or "").strip() == normalized_pattern
                and str(update.get("selected_route") or "").strip() == normalized_route
            ):
                latest = update
        return latest

    def get_latest_relational_edge_strength(
        self,
        *,
        pattern_key: str,
        selected_route: str,
    ) -> float | None:
        latest = self.get_latest_relational_edge_update(
            pattern_key=pattern_key,
            selected_route=selected_route,
        )
        if not latest:
            return None
        strength = latest.get("strength_after")
        try:
            return round(_clamp_unit_interval(float(strength)), 4)
        except (TypeError, ValueError):
            return None

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

    def _load_relational_edge_updates(self) -> list[dict[str, Any]]:
        with self._lock:
            path = self._relational_edge_updates_path()
            if not path.exists():
                return []

            updates: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        updates.append(dict(json.loads(line)))
            return updates

    def _write_relational_edge_updates(
        self,
        updates: list[dict[str, Any]],
    ) -> None:
        self._atomic_write_jsonl(
            self._relational_edge_updates_path(),
            updates,
        )

    # ──────────────────────────────────────────────────────────────
    # RouteSnapshot — versioned evolved route candidates
    # ──────────────────────────────────────────────────────────────

    def _route_snapshots_path(self) -> Path:
        return self.path.with_name("route_snapshots.jsonl")

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
